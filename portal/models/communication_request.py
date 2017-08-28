"""CommunicationRequest model"""
from flask import current_app
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM

from .assessment_status import overall_assessment_status
from .communication import Communication
from ..database import db
from .identifier import Identifier
from .reference import Reference
from ..system_uri import TRUENTH_CR_NAME


# https://www.hl7.org/fhir/valueset-request-status.html
request_status_types = ENUM(
    'draft', 'active', 'suspended', 'cancelled', 'completed',
    'entered-in-error', 'unknown', name='request_statuses',
    create_type=False)


class CommunicationRequest(db.Model):
    """Model representing a FHIR-like CommunicationRequest

    CommunicationRequest is used to capture business rules surrounding
    messages, reminders and other forms of communications.

    As the base event which defines the time often moves due to
    procedures and diagnosis, time deltas are generally persisted
    within the CommunicationRequest rather than a static datetime.

    CommunicationRequests are associated with a set of users by a
    QuestionnaireBank, such that for any user for whom the
    QuestionnaireBank applies, send the communication (unless
    the QuestionnaireBank is completed or expired).

    NB - several exceptions from the FHIR spec exist for this model,
    as the FHIR doesn't well handle time deltas and associations as needed.

    """
    __tablename__ = 'communication_requests'
    id = db.Column(db.Integer, primary_key=True)
    identifiers = db.relationship(
        'Identifier', lazy='dynamic',
        secondary="communication_request_identifiers")
    status = db.Column('status', request_status_types, nullable=False)
    notify_days_after_event = db.Column(db.Integer, nullable=False)

    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=False)
    questionnaire_bank = db.relationship('QuestionnaireBank')

    __table_args__ = (
        UniqueConstraint(
            questionnaire_bank_id, notify_days_after_event,
            name='_communication_request_qb_days'),
    )

    def __str__(self):
        return (
            'CommunicationRequest for {0.questionnaire_bank}'
            ' on {0.notify_days_after_event}'.format(self))

    @property
    def name(self):
        # Specific identifier is used as shorthand for name
        for id in self.identifiers:
            if id.system == TRUENTH_CR_NAME:
                return id.value
        return None

    @property
    def lr_url(self):
        if not self.name:
            return None

        # Waiting on labels and tags in LR - wire up a cheap lookup
        # for the time being.
        lookup = {}
        lookup["Symptom Tracker | 3 Mo Reminder (1)"] = (
            "5424efca-9f24-7ff5-cb41-96c1f6546fab")
        lookup["Symptom Tracker | 3 Mo Reminder (2)"] = (
            "f1c20a1a-c207-7bfb-92b9-ed51abe73ef1")
        lookup["Symptom Tracker | 3 Mo Reminder (3)"] = (
            "b18a5e30-9927-2b33-8db4-e8c2d6e0ad59")
        lookup["Symptom Tracker | 3 Mo Reminder (4)"] = (
            "40ee1906-3099-f468-ea7b-69b50df6ee44")
        lookup["Symptom Tracker | 6 Mo Reminder (1)"] = (
            "d4b493e0-0c2f-9249-19dc-752d29a542a0")
        lookup["Symptom Tracker | 6 Mo Reminder (2)"] = (
            "ed96806d-1d9e-df99-f0e3-7f8372d0ce24")
        lookup["Symptom Tracker | 6 Mo Reminder (3)"] = (
            "0d2376e1-5cda-db40-0c0c-5a5ea1cd90bc")
        lookup["Symptom Tracker | 6 Mo Reminder (4)"] = (
            "d27fe3af-cf2f-585e-b53c-0397e40065be")

        uuid = lookup.get(self.name)
        return (
            "{config[LR_ORIGIN]}/c/portal/truenth/asset/"
            "mail?version=latest&uuid={uuid}".format(
                config=current_app.config, uuid=uuid))

    @classmethod
    def from_fhir(cls, data):
        instance = cls()
        return instance.update_from_fhir(data)

    def update_from_fhir(self, data):
        self.status = data['status']
        self.notify_days_after_event = data['notify_days_after_event']
        if 'identifier' in data:
            for id in data['identifier']:
                identifier = Identifier.from_fhir(id).add_if_not_found()
                if identifier not in self.identifiers.all():
                    self.identifiers.append(identifier)
        self.questionnaire_bank_id = Reference.parse(
            data['questionnaire_bank']).id
        self = self.add_if_not_found(commit_immediately=True)
        return self

    def as_fhir(self):
        d = {}
        d['resourceType'] = 'CommunicationRequest'
        d['status'] = self.status
        d['notify_days_after_event'] = self.notify_days_after_event
        d['questionnaire_bank'] = Reference.questionnaire_bank(
            self.questionnaire_bank_id).as_fhir()
        return d

    def add_if_not_found(self, commit_immediately=False):
        """Add self to database, or return existing

        Queries for similar, adds new if not found.

        @return: the new or matched CommunicationRequest

        """
        existing = CommunicationRequest.query.filter(
            CommunicationRequest.questionnaire_bank_id ==
            self.questionnaire_bank_id).filter(
                CommunicationRequest.notify_days_after_event ==
                self.notify_days_after_event).first()
        if not existing:
            db.session.add(self)
            if commit_immediately:
                db.session.commit()
        else:
            self.id = existing.id
        self = db.session.merge(self)
        return self


class CommunicationRequestIdentifier(db.Model):
    """link table for CommunicationRequest : n identifiers"""
    __tablename__ = 'communication_request_identifiers'
    id = db.Column(db.Integer, primary_key=True)
    communication_request_id = db.Column(db.ForeignKey(
        'communication_requests.id', ondelete='cascade'), nullable=False)
    identifier_id = db.Column(db.ForeignKey(
        'identifiers.id', ondelete='cascade'), nullable=False)

    __table_args__ = (UniqueConstraint(
        'communication_request_id', 'identifier_id',
        name='_communication_request_identifier'),)


def queue_outstanding_messages(user, questionnaire_bank):
    """Lookup and queue any outstanding communications

    Complex task, to determine if a communication should be queued.  Only
    queue if a matching communication doesn't exist, user meets
    preconditions defining event start, and hasn't yet fulfilled the point of
    the communication (such as having completed a questionnaire for which this
    communication is reminding them to do). And then of course, only
    if the notify_days_after_event have passed.

    Messages are queued by adding to the Communications table, with
    'preparation' status.

    """

    def existing_communication(user_id, communication_request_id):
        "Return a matching communication, if found"
        existing = Communication.query.filter(
            Communication.user_id == user_id
        ).filter(
            Communication.communication_request_id == communication_request_id
        ).first()
        return existing

    def unfinished_work(user, questionnaire_bank):
        """Return True if user has oustanding work and valid time remains

        Users may have completed all the related questionnaires, or they may
        have failed to do so prior to expiration.

        :returns: True IFF there is remaining work for the user to complete at
        this time

        """
        if questionnaire_bank.classification != 'baseline':
            raise NotImplementedError('only baseline communication wired up')

        return overall_assessment_status(user.id) in (
            'Due', 'Overdue', 'In Progress')

    def queue_communication(user, communication_request):
        """Create new communication object in preparation state"""

        communication = Communication(
            user_id=user.id,
            status='preparation',
            communication_request_id=communication_request.id)
        db.session.add(communication)
        db.session.commit()

    def event_start(user, questionnaire_bank):
        """Lookup event trigger date - if available

        Depends on QuestionnaireBank context.  If associated
        by organization, return the consent date.  For
        intervention association, use the treatment or biopsy date.

        :returns: UTC event datetime - that is the base value for
        communication calculations, or None if situation doesn't
        apply.

        """
        if questionnaire_bank.organization_id:
            # Questionnaires associated by organization
            # use consent date as event start
            if user.valid_consents and len(list(
                    user.valid_consents)) > 0:
                _consent = user.valid_consents[0]
            if _consent:
                return _consent.audit.timestamp
            else:
                return None

        # TODO Pending work to associate QBs by intervion
        return None

    for request in questionnaire_bank.communication_requests:
        if request.status != 'active':
            continue

        # Continue if matching message was already generated
        if existing_communication(
                user_id=user.id,
                communication_request_id=request.id):
            continue

        # Confirm reason for message remains
        if not unfinished_work(user, questionnaire_bank):
            continue

        basis = event_start(user, questionnaire_bank)
        if basis and datetime.utcnow() - basis >= timedelta(
                days=request.notify_days_after_event):
            queue_communication(user=user, communication_request=request)
