from collections import namedtuple
from html.parser import HTMLParser
import json

from flask import current_app, has_request_context, url_for
from flask_swagger import swagger
import jsonschema
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from ..database import db
from ..date_tools import FHIR_datetime
from ..system_uri import TRUENTH_EXTERNAL_STUDY_SYSTEM
from .audit import Audit
from .encounter import Encounter
from .fhir import bundle_results
from .questionnaire import Questionnaire
from .questionnaire_bank import trigger_date
from .reference import Reference
from .user import User, current_user, patients_query
from .user_consent import consent_withdrawal_dates


class QuestionnaireResponse(db.Model):

    def default_status(context):
        return context.current_parameters['document']['status']

    def default_authored(context):
        return FHIR_datetime.parse(
            context.current_parameters['document']['authored'])

    __tablename__ = 'questionnaire_responses'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    subject = db.relationship("User", back_populates="questionnaire_responses")
    document = db.Column(JSONB)
    encounter_id = db.Column(
        db.ForeignKey('encounters.id', name='qr_encounter_id_fk'),
        nullable=False)
    questionnaire_bank_id = db.Column(
        db.ForeignKey('questionnaire_banks.id'), nullable=True)
    qb_iteration = db.Column(db.Integer(), nullable=True)

    encounter = db.relationship("Encounter", cascade='delete')
    questionnaire_bank = db.relationship("QuestionnaireBank")

    # Fields derived from document content
    status = db.Column(
        ENUM(
            'in-progress',
            'completed',
            name='questionnaire_response_statuses'
        ),
        default=default_status
    )

    authored = db.Column(
        db.DateTime,
        default=default_authored
    )

    def __str__(self):
        """Print friendly format for logging, etc."""
        return "QuestionnaireResponse {0.id} for user {0.subject_id} " \
               "{0.status} {0.authored}".format(self)

    def assign_qb_relationship(self, acting_user_id, qbd_accessor=None):
        """Lookup and assign questionnaire bank and iteration

        On submission, and subsequently when a user's state changes (such as
        the criteria for trigger_date), determine the associated questionnaire
        bank and iteration and assign, or clear if no match is found.

        :param acting_user_id: current driver of process, for audit purposes
        :param qbd_accessor: function to look up appropriate QBD for given QNR
          Takes ``as_of_date`` and ``classification`` parameters

        """
        authored = FHIR_datetime.parse(self.document['authored'])
        if qbd_accessor is None:
            from .qb_status import QB_Status  # avoid cycle
            qbstatus = QB_Status(self.subject, as_of_date=authored)

            def qbstats_current_qbd(as_of_date, classification):
                if as_of_date != authored:
                    raise RuntimeError(
                        "local QB_Status instantiated w/ wrong as_of_date")
                return qbstatus.current_qbd(classification)
            qbd_accessor = qbstats_current_qbd

        initial_qb_id = self.questionnaire_bank_id
        initial_qb_iteration = self.qb_iteration

        # clear both until current values are determined
        self.questionnaire_bank_id, self.qb_iteration = None, None

        qn_ref = self.document.get("questionnaire").get("reference")
        qn_name = qn_ref.split("/")[-1] if qn_ref else None
        qn = Questionnaire.find_by_name(name=qn_name)
        qbd = qbd_accessor(as_of_date=authored, classification=None)
        if qbd and qn and qn.id in (
                q.questionnaire.id for q in
                qbd.questionnaire_bank.questionnaires):
            self.questionnaire_bank_id = qbd.qb_id
            self.qb_iteration = qbd.iteration
        # if a valid qb wasn't found, try the indefinite option
        else:
            qbd = qbd_accessor(
                as_of_date=authored, classification='indefinite')
            if qbd and qn and qn.id in (
                    q.questionnaire.id for q in
                    qbd.questionnaire_bank.questionnaires):
                self.questionnaire_bank_id = qbd.qb_id
                self.qb_iteration = qbd.iteration

        if not self.questionnaire_bank_id:
            current_app.logger.warning(
                "Can't locate QB for patient {}'s questionnaire_response "
                "with reference to given instrument {}".format(
                    self.subject_id, qn_name))
            self.questionnaire_bank_id = None
            self.qb_iteration = None

        if self.questionnaire_bank_id != initial_qb_id or (
                self.qb_iteration != initial_qb_iteration):
            msg = (
                "Updating to qb_id ({}) and qb_iteration ({}) on"
                " questionnaire_response {}".format(
                    self.questionnaire_bank_id, self.qb_iteration,
                    self.id))
            audit = Audit(
                subject_id=self.subject_id, user_id=acting_user_id,
                context='assessment', comment=msg)
            db.session.add(audit)

    @staticmethod
    def purge_qb_relationship(subject_id, acting_user_id):
        """Remove qb association from subject user's QuestionnaireResponses

        An event such as changing consent date potentially alters the
        "visit_name" (i.e. 3 month, baseline, etc.) any existing QNRs
        may have been assigned.  This method removes all such QNR->QB
        associations that may now apply to the wrong QB, forcing subsequent
        recalculation

        """
        audits = []
        matching = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == subject_id).filter(
            QuestionnaireResponse.questionnaire_bank_id.isnot(None))

        for qnr in matching:
            audit = Audit(
                user_id=acting_user_id, subject_id=subject_id,
                context='assessment',
                comment="Removing qb_id:iteration {}:{} from QNR {}".format(
                    qnr.questionnaire_bank_id, qnr.qb_iteration, qnr.id))
            audits.append(audit)
            qnr.questionnaire_bank_id = None
            qnr.qb_iteration = None

        for audit in audits:
            db.session.add(audit)

        db.session.commit()

    @staticmethod
    def by_identifier(identifier):
        """Query for QuestionnaireResponse(s) with given identifier"""
        if not any((identifier.system, identifier.value)):
            raise ValueError("Can't look up null identifier")

        if identifier.system is None:  # FHIR allows null system
            found = QuestionnaireResponse.query.filter(
                QuestionnaireResponse.document['identifier']['system'].is_(
                    None)).filter(
                QuestionnaireResponse.document['identifier']['value']
                == json.dumps(identifier.value))
        else:
            found = QuestionnaireResponse.query.filter(
                QuestionnaireResponse.document['identifier']['system']
                == json.dumps(identifier.system)).filter(
                QuestionnaireResponse.document['identifier']['value']
                == json.dumps(identifier.value))
        return found.order_by(QuestionnaireResponse.id.desc()).all()

    @staticmethod
    def validate_document(document):
        """Validate given JSON document against our swagger schema"""
        swag = swagger(current_app)

        draft4_schema = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'definitions': swag['definitions'],
        }

        validation_schema = 'QuestionnaireResponse'
        # Copy desired schema (to validate against) to outermost dict
        draft4_schema.update(swag['definitions'][validation_schema])
        jsonschema.validate(document, draft4_schema)

    @property
    def document_answered(self):
        """
        Return a QuestionnaireResponse populated with text answers based on codes in valueCoding
        """
        instrument_id = self.document['questionnaire']['reference'].split('/')[-1]
        questionnaire = Questionnaire.find_by_name(name=instrument_id)

        # return original document if no reference Questionnaire available
        if not questionnaire:
            return self.document

        questionnaire_map = questionnaire.questionnaire_code_map()

        document = self.document
        for question in document.get('group', {}).get('question', ()):

            combined_answers = consolidate_answer_pairs(question['answer'])

            # Separate out text and coded answer, then override text
            text_and_coded_answers = []
            for answer in combined_answers:

                # Add text answer before coded answer
                if answer.keys()[0] == 'valueCoding':

                    # Prefer text looked up from code over sibling valueString answer
                    text_answer = questionnaire_map.get(
                        answer['valueCoding']['code'],
                        answer['valueCoding'].get('text')
                    )

                    text_and_coded_answers.append({'valueString': text_answer})

                text_and_coded_answers.append(answer)
            question['answer'] = text_and_coded_answers

        return document


QNR = namedtuple('QNR', [
    'qnr_id', 'qb_id', 'iteration', 'status', 'instrument', 'authored',
    'encounter_id'])


class QNR_results(object):
    """API for QuestionnaireResponses for a user"""

    def __init__(self, user, qb_id=None, qb_iteration=None):
        """Optionally include qb_id and qb_iteration to limit"""
        self.user = user
        self.qb_id = qb_id
        self.qb_iteration = qb_iteration
        self._qnrs = None

    @property
    def qnrs(self):
        """Return cached qnrs or query first time"""
        if self._qnrs is not None:
            return self._qnrs

        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == self.user.id).with_entities(
            QuestionnaireResponse.id,
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.authored,
            QuestionnaireResponse.encounter_id).order_by(
            QuestionnaireResponse.authored)
        if self.qb_id:
            query = query.filter(
                QuestionnaireResponse.questionnaire_bank_id == self.qb_id
            ).filter(
                QuestionnaireResponse.qb_iteration == self.qb_iteration)
        self._qnrs = []
        for qnr in query:
            self._qnrs.append(QNR(
                qnr_id=qnr.id,
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=qnr.instrument_id.split('/')[-1],
                authored=qnr.authored,
                encounter_id=qnr.encounter_id))
        return self._qnrs

    def assign_qb_relationships(self, qb_generator):
        """Associate any QNRs with respective qbs

        Typically, done at time of QNR POST - however occasionally events
        force a renewed lookup of QNR -> QB association.

        """
        from .qb_timeline import calc_and_adjust_expired, calc_and_adjust_start

        if self.qb_id:
            raise ValueError(
                "Can't associate results when restricted to single QB")

        qbs = [qb for qb in qb_generator(self.user)]
        indef_qbs = [qb for qb in qb_generator(
            self.user, classification="indefinite")]

        td = trigger_date(user=self.user)
        old_td, withdrawal_date = consent_withdrawal_dates(self.user)
        if not td and old_td:
            td = old_td

        def qbd_accessor(as_of_date, classification):
            """Simplified qbd lookup consults only assigned qbs"""
            if classification == 'indefinite':
                container = indef_qbs
            else:
                container = qbs

            # Loop until date matching qb found, break if beyond
            for qbd in container:
                qb_start = calc_and_adjust_start(
                    user=self.user, qbd=qbd, initial_trigger=td)
                qb_expired = calc_and_adjust_expired(
                    user=self.user, qbd=qbd, initial_trigger=td)
                if as_of_date < qb_start:
                    continue
                if qb_start <= as_of_date < qb_expired:
                    return qbd
                if qb_expired > as_of_date:
                    break

        # typically triggered from updating task job - use system
        # as acting user in audits, if no current user is available
        acting_user = None
        if has_request_context():
            acting_user = current_user()
        if not acting_user:
            acting_user = User.query.filter_by(email='__system__').first()
        for qnr in self.qnrs:
            QuestionnaireResponse.query.get(
                qnr.qnr_id).assign_qb_relationship(
                acting_user_id=acting_user.id, qbd_accessor=qbd_accessor)
        db.session.commit()

        # Force fresh lookup on next access
        self._qnrs = None

    def qnrs_missing_qb_association(self):
        """Returns true if any QNRs exist without qb associations

        Business rules mandate purging qnr->qb association following
        events such as a change of consent date.  This method can be
        used to determine if qnr->qb association lookup may be required.

        NB - it can be legitimate for QNRs to never have a QB association,
        such as systems that don't define QBs for all assessments or those
        taken prior to a new trigger date.

        :returns: True if at least one QNR exists for the user missing qb_id

        """
        associated = [qnr for qnr in self.qnrs if qnr.qb_id is not None]
        return len(self.qnrs) != len(associated)

    def earliest_result(self, qb_id, iteration):
        """Returns timestamp of earliest result for given params, or None"""
        for qnr in self.qnrs:
            if (qnr.qb_id == qb_id and
                    qnr.iteration == iteration):
                return qnr.authored

    def entry_method(self):
        """Returns first entry method found in results, or None"""
        for qnr in self.qnrs:
            if qnr.encounter_id is not None:
                encounter = Encounter.query.get(qnr.encounter_id)
                if encounter.type and len(encounter.type):
                    return encounter.type[0].code

    def required_qs(self, qb_id):
        """Return required list (order counts) of Questionnaires for QB"""
        from .questionnaire_bank import QuestionnaireBank  # avoid import cyc.
        qb = QuestionnaireBank.query.get(qb_id)
        return [q.name for q in qb.questionnaires]

    def completed_qs(self, qb_id, iteration):
        """Return set of completed Questionnaire results for given QB"""
        return {qnr.instrument for qnr in self.qnrs if
                qnr.qb_id == qb_id
                and qnr.iteration == iteration
                and qnr.status == "completed"}

    def partial_qs(self, qb_id, iteration):
        """Return set of partial Questionnaire results for given QB"""
        return {qnr.instrument for qnr in self.qnrs if
                qnr.qb_id == qb_id
                and qnr.iteration == iteration
                and qnr.status == "in-progress"}

    def completed_date(self, qb_id, iteration):
        """Returns timestamp when named QB was completed, or None"""
        required = set(self.required_qs(qb_id))
        have = self.completed_qs(qb_id=qb_id, iteration=iteration)
        if required - have:
            # incomplete set
            return None
        # Return time when last completed in required came in
        germane = [qnr for qnr in self.qnrs if
                   qnr.qb_id == qb_id
                   and qnr.iteration == iteration
                   and qnr.status == "completed"]
        for item in germane:
            if item.instrument in required:
                required.remove(item.instrument)
            if not required:
                return item.authored
        raise RuntimeError("should have found authored for all required")


class QNR_indef_results(QNR_results):
    """Specialized for indefinite QB"""

    def __init__(self, user, qb_id):
        self.user = user
        query = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == user.id).filter(
            QuestionnaireResponse.questionnaire_bank_id == qb_id
        ).with_entities(
            QuestionnaireResponse.questionnaire_bank_id,
            QuestionnaireResponse.qb_iteration,
            QuestionnaireResponse.status,
            QuestionnaireResponse.document[
                ('questionnaire', 'reference')].label('instrument_id'),
            QuestionnaireResponse.authored,
            QuestionnaireResponse.encounter_id).order_by(
            QuestionnaireResponse.authored)

        self.qnrs = []
        for qnr in query:
            self.qnrs.append(QNR(
                qb_id=qnr.questionnaire_bank_id,
                iteration=qnr.qb_iteration,
                status=qnr.status,
                instrument=qnr.instrument_id.split('/')[-1],
                authored=qnr.authored,
                encounter_id=qnr.encounter_id))


def aggregate_responses(instrument_ids, current_user, patch_dstu2=False):
    """Build a bundle of QuestionnaireResponses

    :param instrument_ids: list of instrument_ids to restrict results to
    :param current_user: user making request, necessary to restrict results
        to list of patients the current_user has permission to see

    """
    from .qb_timeline import qb_status_visit_name  # avoid cycle

    # Gather up the patient IDs for whom current user has 'view' permission
    user_ids = patients_query(
        current_user, include_test_role=False).with_entities(User.id)

    annotated_questionnaire_responses = []
    questionnaire_responses = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.subject_id.in_(user_ids)).order_by(
        QuestionnaireResponse.authored.desc())

    if instrument_ids:
        instrument_filters = (
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
            for instrument_id in instrument_ids
        )
        questionnaire_responses = questionnaire_responses.filter(
            or_(*instrument_filters))

    patient_fields = ("careProvider", "identifier")
    system_filter = current_app.config.get('REPORTING_IDENTIFIER_SYSTEMS')
    for questionnaire_response in questionnaire_responses:
        document = questionnaire_response.document_answered.copy()
        subject = questionnaire_response.subject
        encounter = questionnaire_response.encounter
        encounter_fhir = encounter.as_fhir()
        document["encounter"] = encounter_fhir

        document["subject"] = {
            k: v for k, v in subject.as_fhir().items() if k in patient_fields
        }

        if subject.organizations:
            providers = []
            for org in subject.organizations:
                org_ref = Reference.organization(org.id).as_fhir()
                identifiers = [i.as_fhir() for i in org.identifiers if
                               i.system in system_filter]
                if identifiers:
                    org_ref['identifier'] = identifiers
                providers.append(org_ref)
            document["subject"]["careProvider"] = providers

        _, timepoint = qb_status_visit_name(subject.id, encounter.start_time)
        document["timepoint"] = timepoint

        # Hack: add missing "resource" wrapper for DTSU2 compliance
        # Remove when all interventions compliant
        if patch_dstu2:
            document = {
                'resource': document,
                # Todo: return URL to individual QuestionnaireResponse resource
                'fullUrl': url_for(
                    '.assessment',
                    patient_id=subject.id,
                    _external=True,
                ),
            }

        annotated_questionnaire_responses.append(document)

    return bundle_results(elements=annotated_questionnaire_responses)


def qnr_document_id(
        subject_id, questionnaire_bank_id, questionnaire_name, iteration,
        status):
    """Return document['identifier'] for matching QuestionnaireResponse

    Using the given filter data to look for a matching QuestionnaireResponse.
    Expecting to find exactly one, or raises NoResultFound

    :return: the document identifier value, typically a string

    """
    qnr = QuestionnaireResponse.query.filter(
        QuestionnaireResponse.status == status).filter(
        QuestionnaireResponse.subject_id == subject_id).filter(
        QuestionnaireResponse.document[
            ('questionnaire', 'reference')
        ].astext.endswith(questionnaire_name)).filter(
        QuestionnaireResponse.questionnaire_bank_id ==
        questionnaire_bank_id).with_entities(
        QuestionnaireResponse.document[(
            'identifier', 'value')])
    if iteration is not None:
        qnr = qnr.filter(QuestionnaireResponse.qb_iteration == iteration)
    else:
        qnr = qnr.filter(QuestionnaireResponse.qb_iteration.is_(None))

    return qnr.one()[0]


def consolidate_answer_pairs(answers):
    """
    Merge paired answers (code and corresponding text) into single
        row/answer

    Codes are the preferred way of referring to options but option text
        (at the time of administration) may be submitted alongside coded
        answers for ease of display
    """

    answer_types = [a.keys()[0] for a in answers]

    # Exit early if assumptions not met
    if (
        len(answers) % 2 or
        answer_types.count('valueCoding') != answer_types.count('valueString')
    ):
        return answers

    filtered_answers = []
    for pair in zip(*[iter(answers)] * 2):
        # Sort so first pair is always valueCoding
        pair = sorted(pair, key=lambda k: k.keys()[0])
        coded_answer, string_answer = pair

        coded_answer['valueCoding']['text'] = string_answer['valueString']

        filtered_answers.append(coded_answer)

    return filtered_answers


def generate_qnr_csv(qnr_bundle):
    """Generate a CSV from a bundle of QuestionnaireResponses"""

    csv_null_value = r"\N"

    class HTMLStripper(HTMLParser):
        """Subclass of HTMLParser for stripping HTML tags"""

        def __init__(self):
            self.reset()
            self.strict = False
            self.convert_charrefs = True
            self.fed = []

        def handle_data(self, data):
            self.fed.append(data)

        def get_data(self):
            return ' '.join(self.fed)

    def strip_tags(html):
        """Strip HTML tags from strings. Inserts whitespace if necessary."""

        s = HTMLStripper()
        s.feed(html)
        stripped = s.get_data()
        # Remove extra spaces
        return ' '.join(filter(None, stripped.split(' ')))

    def get_identifier(id_list, **kwargs):
        """Return first identifier object matching kwargs"""
        for identifier in id_list:
            for k, v in kwargs.items():
                if identifier.get(k) != v:
                    break
            else:
                return identifier['value']
        return None

    def get_site(qnr_data):
        """Return (external id, name) of first organization, else Nones"""
        try:
            provider = qnr_data['subject']['careProvider'][0]
            org_name = provider['display']
            if 'identifier' in provider:
                id_value = provider['identifier'][0]['value']
            else:
                id_value = None
            return id_value, org_name
        except (KeyError, IndexError):
            return None, None


    def entry_method(row_data, qnr_data):
        # Todo: replace with EC.PAPER CodeableConcept
        if (
                'type' in qnr_data['encounter'] and
                'paper' in (c.get('code') for c in
                            qnr_data['encounter']['type'])
        ):
            return 'enter manually - paper'
        if row_data.get('truenth_subject_id') == row_data.get('author_id'):
            return 'online'
        else:
            return 'enter manually - interview assisted'

    def author_role(row_data, qnr_data):
        if row_data.get('truenth_subject_id') == row_data.get('author_id'):
            return 'Subject'
        else:
            return 'Site Resource'

    columns = (
        'identifier',
        'status',
        'study_id',
        'site_id',
        'site_name',
        'truenth_subject_id',
        'author_id',
        'author_role',
        'entry_method',
        'authored',
        'timepoint',
        'instrument',
        'question_code',
        'answer_code',
        'option_text',
        'other_text',
    )

    yield ','.join('"' + column + '"' for column in columns) + '\n'
    for qnr in qnr_bundle['entry']:
        site_id, site_name = get_site(qnr)
        row_data = {
            'identifier': qnr['identifier']['value'],
            'status': qnr['status'],
            'truenth_subject_id': get_identifier(
                qnr['subject']['identifier'],
                use='official'
            ),
            'author_id': qnr['author']['reference'].split('/')[-1],
            'site_id': site_id,
            'site_name': site_name,
            # Todo: correctly pick external study of interest
            'study_id': get_identifier(
                qnr['subject']['identifier'],
                system=TRUENTH_EXTERNAL_STUDY_SYSTEM
            ),
            'authored': qnr['authored'],
            'timepoint': qnr['timepoint'],
            'instrument': qnr['questionnaire']['reference'].split('/')[-1],
        }
        row_data.update({
            'entry_method': entry_method(row_data, qnr),
            'author_role': author_role(row_data, qnr),
        })
        for question in qnr['group']['question']:
            row_data.update({
                'question_code': question['linkId'],
                'answer_code': None,
                'option_text': None,
                'other_text': None,
            })

            answers = consolidate_answer_pairs(question['answer']) or ({},)

            for answer in answers:
                if answer:
                    # Use first value of answer (most are single-entry dicts)
                    answer_data = {'other_text': answer.values()[0]}

                    # ...unless nested code (ie valueCode)
                    if answer.keys()[0] == 'valueCoding':
                        answer_data.update({
                            'answer_code': answer['valueCoding']['code'],

                            # Add supplementary text added earlier
                            # Todo: lookup option text in stored Questionnaire
                            'option_text': strip_tags(
                                answer['valueCoding'].get('text', None)),
                            'other_text': None,
                        })
                    row_data.update(answer_data)

                row = []
                for column_name in columns:
                    column = row_data.get(column_name)
                    column = csv_null_value if column is None else column

                    # Handle JSON column escaping/enclosing
                    if not isinstance(column, str):
                        column = json.dumps(column).replace('"', '""')
                    row.append('"' + column + '"')

                yield ','.join(row) + '\n'
