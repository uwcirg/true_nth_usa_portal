"""Tasks module

All tasks run via external message queue (via celery) are defined
within.

NB: a celery worker must be started for these to ever return.  See
`celery_worker.py`

"""
from celery.utils.log import get_task_logger
from datetime import datetime
from flask import current_app
import json
from requests import Request, Session
from requests.exceptions import RequestException
from smtplib import SMTPRecipientsRefused
from sqlalchemy import and_
from traceback import format_exc

from .audit import auditable_event
from .database import db
from .dogpile_cache import dogpile_cache
from factories.celery import create_celery
from factories.app import create_app
from .models.assessment_status import invalidate_assessment_status_cache
from .models.assessment_status import overall_assessment_status
from .models.app_text import app_text, MailResource, SiteSummaryEmail_ATMA
from .models.communication import Communication, load_template_args
from .models.communication_request import queue_outstanding_messages
from .models.message import EmailMessage
from .models.organization import Organization, OrgTree
from .models.reporting import get_reporting_stats, overdue_stats_by_org
from .models.reporting import generate_overdue_table_html
from .models.role import Role, ROLE
from .models.questionnaire_bank import QuestionnaireBank
from .models.user import User, UserRoles
from .models.scheduled_job import update_job_status

# To debug, stop the celeryd running out of /etc/init, start in console:
#   celery worker -A portal.celery_worker.celery --loglevel=debug
# Import rdb and use like pdb:
#   from celery.contrib import rdb
#   rdb.set_trace()
# Follow instructions from celery console, i.e. telnet 127.0.0.1 6900

logger = get_task_logger(__name__)

celery = create_celery(create_app())


@celery.task(name="tasks.add")
def add(x, y):
    return x + y


@celery.task(name="tasks.info")
def info():
    return "BROKER_URL: {} <br/> SERVER_NAME: {}".format(
        current_app.config.get('BROKER_URL'),
        current_app.config.get('SERVER_NAME'))


@celery.task(name="tasks.post_request", bind=True)
def post_request(self, url, data, timeout=10, retries=3):
    """Wrap requests.post for asyncronous posts - includes timeout & retry"""
    logger.debug("task: %s retries:%s", self.request.id, self.request.retries)

    s = Session()
    req = Request('POST', url, data=data)
    prepped = req.prepare()
    try:
        resp = s.send(prepped, timeout=timeout)
        if resp.status_code < 400:
            logger.info("{} received from {}".format(resp.status_code, url))
        else:
            logger.error("{} received from {}".format(resp.status_code, url))

    except RequestException as exc:
        """Typically raised on timeout or connection error

        retry after countdown seconds unless retry threshold has been exceeded
        """
        logger.warn("{} on {}".format(exc.message, url))
        if self.request.retries < retries:
            raise self.retry(exc=exc, countdown=20)
        else:
            logger.error(
                "max retries exceeded for {}, last failure: {}".format(
                    url, exc))
    except Exception as exc:
        logger.error("Unexpected exception on {} : {}".format(url, exc))


@celery.task
def test(job_id=None):
    update_current_job(job_id, 'test', status="success")
    return "Test task complete."


@celery.task
def test_args(job_id=None, *args, **kwargs):
    alist = ",".join(args)
    klist = json.dumps(kwargs)
    msg = "Test task complete. - {} - {}".format(alist, klist)
    update_current_job(job_id, 'test_args', status=msg)
    return msg


@celery.task
def cache_reporting_stats(job_id=None):
    """Populate reporting dashboard stats cache

    Reporting stats can be a VERY expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potenailly
    stale cache.  Expected to be called as a scheduled job.

    """
    try:
        message = "failed"
        before = datetime.now()
        dogpile_cache.invalidate(get_reporting_stats)
        dogpile_cache.refresh(get_reporting_stats)
        duration = datetime.now() - before
        message = (
            'Reporting stats updated in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
    except Exception as exc:
        message = ("Unexpected exception in `cache_reporting_stats` "
                     "on {} : {}".format(job_id, exc))
        logger.error(message)
        logger.error(format_exc())
    update_current_job(job_id, 'cache_reporting_stats', status=message)
    return message


@celery.task
def cache_assessment_status(job_id=None):
    """Populate assessment status cache

    Assessment status is an expensive lookup - cached for an hour
    at a time.  This task is responsible for renewing the potenailly
    stale cache.  Expected to be called as a scheduled job.

    """
    try:
        message = "failed"
        before = datetime.now()
        update_patient_loop(update_cache=True, queue_messages=False)
        duration = datetime.now() - before
        message = (
            'Assessment Cache updated in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
    except Exception as exc:
        message = ("Unexpected exception in `cache_assessment_status` "
                     "on {} : {}".format(job_id, exc))
        logger.error(message)
        logger.error(format_exc())
    update_current_job(job_id, 'cache_assessment_status', status=message)
    return message


@celery.task
def prepare_communications(job_id=None):
    """Move any ready communications into prepared state """
    try:
        message = "failed"
        before = datetime.now()
        update_patient_loop(update_cache=False, queue_messages=True)
        duration = datetime.now() - before
        message = (
            'Prepared messages queued in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
    except Exception as exc:
        message = ("Unexpected exception in `prepare_communications` "
                     "on {} : {}".format(job_id, exc))
        logger.error(message)
        logger.error(format_exc())
    update_current_job(job_id, 'prepare_communications', status=message)
    return message


def update_patient_loop(update_cache=True, queue_messages=True):
    """Function to loop over valid patients and update as per settings

    Typically called as a scheduled_job - also directly from tests
    """
    patient_role_id = Role.query.filter(
        Role.name == ROLE.PATIENT).with_entities(Role.id).first()[0]
    valid_patients = User.query.join(
        UserRoles).filter(
            and_(User.id == UserRoles.user_id,
                 User.deleted_id.is_(None),
                 UserRoles.role_id == patient_role_id))

    now = datetime.utcnow()
    for user in valid_patients:
        if update_cache:
            dogpile_cache.invalidate(overall_assessment_status, user.id)
            dogpile_cache.refresh(overall_assessment_status, user.id)
        if queue_messages:
            if not user.email or '@' not in user.email:
                # can't send to users w/o legit email
                continue
            qbd = QuestionnaireBank.most_current_qb(user=user, as_of_date=now)
            if qbd.questionnaire_bank:
                queue_outstanding_messages(
                    user=user,
                    questionnaire_bank=qbd.questionnaire_bank,
                    iteration_count=qbd.iteration)
    db.session.commit()


@celery.task
def send_queued_communications(job_id=None):
    "Look for communication objects ready to send"
    try:
        before = datetime.now()
        send_messages()
        duration = datetime.now() - before
        message = (
            'Sent queued messages in {0.seconds} seconds'.format(duration))
        current_app.logger.debug(message)
    except Exception as exc:
        message = ("Unexpected exception in `send_queued_communications` "
                   "on {} : {}".format(job_id, exc))
        logger.error(message)
        logger.error(format_exc())
    update_current_job(job_id, 'send_queued_communications', status=message)
    return message


def send_messages():
    """Function to send all queued messages

    Typically called as a scheduled_job - also directly from tests
    """
    ready = Communication.query.filter(Communication.status == 'preparation')
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        db.session.commit()


def send_user_messages(email, force_update=False):
    """Send queued messages to only given user (if found)

    @param email: to process
    @param force_update: set True to force reprocessing of cached
    data and queue any messages previously overlooked.

    Triggers a send for any messages found in a prepared state ready
    for transmission.

    """
    if force_update:
        user = User.query.filter(User.email == email).one()
        invalidate_assessment_status_cache(user_id=user.id)
        qbd = QuestionnaireBank.most_current_qb(
            user=user, as_of_date=datetime.utcnow())
        if qbd.questionnaire_bank:
            queue_outstanding_messages(
                user=user,
                questionnaire_bank=qbd.questionnaire_bank,
                iteration_count=qbd.iteration)
    count = 0
    ready = Communication.query.join(User).filter(
        Communication.status == 'preparation').filter(User.email == email)
    for communication in ready:
        current_app.logger.debug("Collate ready communication {}".format(
            communication))
        communication.generate_and_send()
        db.session.commit()
        count += 1
    message = "Sent {} messages to {}".format(count, email)
    if force_update:
        message += " after forced update"
    return message


@celery.task
def send_questionnaire_summary(job_id, cutoff_days, org_id):
    "Generate and send a summary of questionnaire counts to all Staff in org"
    try:
        before = datetime.now()
        error_emails = generate_and_send_summaries(cutoff_days, org_id)
        duration = datetime.now() - before
        message = (
            'Sent summary emails in {0.seconds} seconds.'.format(duration))
        if error_emails:
            message += ('\nUnable to reach recipient(s): '
                        '{}'.format(', '.join(error_emails)))
            logger.error(message)
        else:
            logger.debug(message)
    except Exception as exc:
        message = ("Unexpected exception in `send_questionnaire_summary` "
                   "on {} : {}".format(job_id, exc))
        logger.error(message)
        logger.error(format_exc())
    update_current_job(job_id, 'send_questionnaire_summary', status=message)
    return message


def generate_and_send_summaries(cutoff_days, org_id):
    ostats = overdue_stats_by_org()
    cutoffs = [int(i) for i in cutoff_days.split(',')]
    error_emails = set()

    ot = OrgTree()
    top_org = Organization.query.get(org_id)
    if not top_org:
        raise ValueError("No org with ID {} found.".format(org_id))
    name_key = SiteSummaryEmail_ATMA.name_key(org=top_org.name)

    for user in User.query.filter_by(deleted_id=None).all():
        if (user.has_role(ROLE.STAFF) and user.email and (u'@' in user.email)
                and (top_org in ot.find_top_level_org(user.organizations))):
            args = load_template_args(user=user)
            args['eproms_site_summary_table'] = generate_overdue_table_html(
                cutoff_days=cutoffs,
                overdue_stats=ostats,
                user=user,
                top_org=top_org)
            summary_email = MailResource(app_text(name_key), variables=args)
            em = EmailMessage(recipients=user.email,
                              sender=current_app.config['MAIL_DEFAULT_SENDER'],
                              subject=summary_email.subject,
                              body=summary_email.body)
            try:
                em.send_message()
            except SMTPRecipientsRefused as exc:
                msg = ("Error sending site summary email to {}: "
                       "{}".format(user.email, exc))

                sys = User.query.filter_by(email='__system__').first()

                auditable_event(message=msg,
                                user_id=(sys.id if sys else user.id),
                                subject_id=user.id,
                                context="user")

                current_app.logger.error(msg)
                for email in exc[0]:
                    error_emails.add(email)

    return error_emails or None


def update_current_job(job_id, func_name, runtime=None, status=None):
    try:
        update_job_status(job_id, runtime=runtime, status=status)
    except Exception as exc:
        logger.error("Failed to update job {} for task `{}`:"
                     " {}".format(job_id, func_name, exc))
