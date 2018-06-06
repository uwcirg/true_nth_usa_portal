"""Module to test assessment_status"""
from datetime import datetime
from random import choice
from string import ascii_letters

from dateutil.relativedelta import relativedelta
from flask_webtest import SessionScope
from portal.extensions import db
from portal.models.assessment_status import (
    AssessmentStatus,
    invalidate_assessment_status_cache,
)
from portal.models.audit import Audit
from portal.models.encounter import Encounter
from portal.models.fhir import CC, QuestionnaireResponse, qnr_document_id
from portal.models.intervention import INTERVENTION
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.recur import Recur
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user import get_user
from portal.system_uri import ICHOM
from sqlalchemy.orm.exc import NoResultFound
from tests import TEST_USER_ID, TestCase, associative_backdate

now = datetime.utcnow()


def mock_qr(
        instrument_id, status='completed', timestamp=None, qb=None,
        doc_id=None):
    if not doc_id:
        doc_id = ''.join(choice(ascii_letters) for _ in range(10))
    timestamp = timestamp or datetime.utcnow()
    qr_document = {
        "questionnaire": {
            "display": "Additional questions",
            "reference":
            "https://{}/api/questionnaires/{}".format(
                'SERVER_NAME', instrument_id)},
        "identifier": {
            "use": "official",
            "label": "cPRO survey session ID",
            "value": doc_id,
            "system": "https://stg-ae.us.truenth.org/eproms-demo"}
    }

    enc = Encounter(status='planned', auth_method='url_authenticated',
                    user_id=TEST_USER_ID, start_time=timestamp)
    with SessionScope(db):
        db.session.add(enc)
        db.session.commit()
    enc = db.session.merge(enc)
    qb = qb or QuestionnaireBank.most_current_qb(get_user(TEST_USER_ID),
                                                 timestamp).questionnaire_bank
    qr = QuestionnaireResponse(
        subject_id=TEST_USER_ID,
        status=status,
        authored=timestamp,
        document=qr_document,
        encounter_id=enc.id,
        questionnaire_bank=qb)
    with SessionScope(db):
        db.session.add(qr)
        db.session.commit()
    invalidate_assessment_status_cache(TEST_USER_ID)


localized_instruments = set(['eproms_add', 'epic26', 'comorb'])
metastatic_baseline_instruments = set([
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi', 'epic23', 'prems'])
metastatic_indefinite_instruments = set(['irondemog'])
metastatic_3 = set([
    'eortc', 'eproms_add', 'ironmisc'])
metastatic_4 = set([
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi'])
metastatic_6 = set([
    'eortc', 'eproms_add', 'ironmisc', 'factfpsi', 'epic23', 'prems'])
symptom_tracker_instruments = set(['epic26', 'eq5d', 'maxpc', 'pam'])


def mock_questionnairebanks(eproms_or_tnth):
    """Create a series of near real world questionnaire banks

    :param eproms_or_tnth: controls which set of questionnairebanks are
        generated.  As restrictions exist, such as two QBs with the same
        classification can't have the same instrument, it doesn't work to mix
        them.

    """
    if eproms_or_tnth == 'eproms':
        return mock_eproms_questionnairebanks()
    elif eproms_or_tnth == 'tnth':
        return mock_tnth_questionnairebanks()
    else:
        raise ValueError('expecting `eproms` or `tntn`, not `{}`'.format(
            eproms_or_tnth))


def mock_eproms_questionnairebanks():
    # Define base ResearchProtocols
    localized_protocol = ResearchProtocol(name='localized_protocol')
    metastatic_protocol = ResearchProtocol(name='metastatic_protocol')
    with SessionScope(db):
        db.session.add(localized_protocol)
        db.session.add(metastatic_protocol)
        db.session.commit()
    localized_protocol = db.session.merge(localized_protocol)
    metastatic_protocol = db.session.merge(metastatic_protocol)
    locpro_id = localized_protocol.id
    metapro_id = metastatic_protocol.id

    # Define test Orgs and QuestionnaireBanks for each group
    localized_org = Organization(name='localized')
    localized_org.research_protocols.append(localized_protocol)
    metastatic_org = Organization(name='metastatic')
    metastatic_org.research_protocols.append(metastatic_protocol)

    # from https://docs.google.com/spreadsheets/d/\
    # 1oJ8HKfMHOdXkSshjRlr8lFXxT4aUHX5ntxnKMgf50wE/edit#gid=1339608238
    three_q_recur = Recur(
        start='{"months": 3}', cycle_length='{"months": 6}',
        termination='{"months": 24}')
    four_q_recur1 = Recur(
        start='{"months": 6}', cycle_length='{"years": 1}',
        termination='{"months": 21}')
    four_q_recur2 = Recur(
        start='{"months": 30}', cycle_length='{"years": 1}',
        termination='{"months": 33}')
    six_q_recur = Recur(
        start='{"years": 1}', cycle_length='{"years": 1}',
        termination='{"years": 3, "months": 3}')

    for name in (localized_instruments.union(*(
            metastatic_baseline_instruments,
            metastatic_indefinite_instruments,
            metastatic_3,
            metastatic_4,
            metastatic_6))):
        TestCase.add_questionnaire(name=name)

    with SessionScope(db):
        db.session.add(localized_org)
        db.session.add(metastatic_org)
        db.session.add(three_q_recur)
        db.session.add(four_q_recur1)
        db.session.add(four_q_recur2)
        db.session.add(six_q_recur)
        db.session.commit()
    localized_org, metastatic_org = map(
        db.session.merge, (localized_org, metastatic_org))
    three_q_recur = db.session.merge(three_q_recur)
    four_q_recur1 = db.session.merge(four_q_recur1)
    four_q_recur2 = db.session.merge(four_q_recur2)
    six_q_recur = db.session.merge(six_q_recur)

    # Localized baseline
    l_qb = QuestionnaireBank(
        name='localized',
        classification='baseline',
        research_protocol_id=locpro_id,
        start='{"days": 0}',
        overdue='{"days": 7}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(localized_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        l_qb.questionnaires.append(qbq)

    # Metastatic baseline
    mb_qb = QuestionnaireBank(
        name='metastatic',
        classification='baseline',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_baseline_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mb_qb.questionnaires.append(qbq)

    # Metastatic indefinite
    mi_qb = QuestionnaireBank(
        name='metastatic_indefinite',
        classification='indefinite',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        expired='{"years": 50}')
    for rank, instrument in enumerate(metastatic_indefinite_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mi_qb.questionnaires.append(qbq)

    # Metastatic recurring 3
    mr3_qb = QuestionnaireBank(
        name='metastatic_recurring3',
        classification='recurring',
        research_protocol_id=metapro_id,
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}',
        recurs=[three_q_recur])
    for rank, instrument in enumerate(metastatic_3):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr3_qb.questionnaires.append(qbq)

    # Metastatic recurring 4
    mr4_qb = QuestionnaireBank(
        name='metastatic_recurring4',
        classification='recurring',
        research_protocol_id=metapro_id,
        recurs=[four_q_recur1, four_q_recur2],
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_4):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr4_qb.questionnaires.append(qbq)

    # Metastatic recurring 6
    mr6_qb = QuestionnaireBank(
        name='metastatic_recurring6',
        classification='recurring',
        research_protocol_id=metapro_id,
        recurs=[six_q_recur],
        start='{"days": 0}',
        overdue='{"days": 30}',
        expired='{"months": 3}')
    for rank, instrument in enumerate(metastatic_6):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        mr6_qb.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(l_qb)
        db.session.add(mb_qb)
        db.session.add(mi_qb)
        db.session.add(mr3_qb)
        db.session.add(mr4_qb)
        db.session.add(mr6_qb)
        db.session.commit()


def mock_tnth_questionnairebanks():
    for name in (symptom_tracker_instruments):
        TestCase.add_questionnaire(name=name)

    # Symptom Tracker Baseline
    self_management = INTERVENTION.SELF_MANAGEMENT
    st_qb = QuestionnaireBank(
        name='symptom_tracker',
        classification='baseline',
        intervention_id=self_management.id,
        start='{"days": 0}',
        expired='{"months": 3}'
    )
    for rank, instrument in enumerate(symptom_tracker_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        st_qb.questionnaires.append(qbq)

    # Symptom Tracker Recurrence
    st_recur = Recur(
        start='{"months": 3}', cycle_length='{"months": 3}',
        termination='{"months": 27}')

    with SessionScope(db):
        db.session.add(st_qb)
        db.session.add(st_recur)
        db.session.commit()

    self_management = INTERVENTION.SELF_MANAGEMENT
    st_recur_qb = QuestionnaireBank(
        name='symptom_tracker_recurring',
        classification='recurring',
        intervention_id=self_management.id,
        start='{"days": 0}',
        expired='{"months": 3}',
        recurs=[st_recur]
    )
    for rank, instrument in enumerate(symptom_tracker_instruments):
        q = Questionnaire.find_by_name(name=instrument)
        qbq = QuestionnaireBankQuestionnaire(questionnaire=q, rank=rank)
        st_recur_qb.questionnaires.append(qbq)
    with SessionScope(db):
        db.session.add(st_recur_qb)
        db.session.commit()


class TestQuestionnaireSetup(TestCase):
    "Base for test classes needing mock questionnaire setup"

    eproms_or_tnth = 'eproms'  # modify in child class to test `tnth`

    def setUp(self):
        super(TestQuestionnaireSetup, self).setUp()
        mock_questionnairebanks(self.eproms_or_tnth)
        if self.eproms_or_tnth == 'eproms':
            self.localized_org_id = Organization.query.filter_by(
                name='localized').one().id
            self.metastatic_org_id = Organization.query.filter_by(
                name='metastatic').one().id

    def mark_localized(self):
        self.test_user.organizations.append(Organization.query.get(
            self.localized_org_id))

    def mark_metastatic(self):
        self.test_user.organizations.append(Organization.query.get(
            self.metastatic_org_id))


class TestAssessmentStatus(TestQuestionnaireSetup):

    def test_qnr_id(self):
        qb = QuestionnaireBank.query.first()
        mock_qr(
            instrument_id='irondemog',
            status='in-progress', qb=qb,
            doc_id='two11')
        qb = db.session.merge(qb)
        result = qnr_document_id(
            TEST_USER_ID, qb.id, 'irondemog', 'in-progress')
        self.assertEquals(result, 'two11')

    def test_qnr_id_missing(self):
        qb = QuestionnaireBank.query.first()
        qb = db.session.merge(qb)
        with self.assertRaises(NoResultFound):
            result = qnr_document_id(
                TEST_USER_ID, qb.id, 'irondemog', 'in-progress')

    def test_enrolled_in_metastatic(self):
        """metastatic should include baseline and indefinite"""
        self.bless_with_basics()
        self.mark_metastatic()
        user = db.session.merge(self.test_user)

        a_s = AssessmentStatus(user=user, as_of_date=now)
        self.assertTrue(a_s.enrolled_in_classification('baseline'))
        self.assertTrue(a_s.enrolled_in_classification('indefinite'))

    def test_enrolled_in_localized(self):
        """localized should include baseline but not indefinite"""
        self.bless_with_basics()
        self.mark_localized()
        user = db.session.merge(self.test_user)

        a_s = AssessmentStatus(user=user, as_of_date=now)
        self.assertTrue(a_s.enrolled_in_classification('baseline'))
        self.assertFalse(a_s.enrolled_in_classification('indefinite'))

    def test_localized_using_org(self):
        self.bless_with_basics()
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)

        # confirm appropriate instruments
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment()),
            localized_instruments)

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(instrument_id='eproms_add')
        mock_qr(instrument_id='epic26')
        mock_qr(instrument_id='comorb')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "Completed")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))

    def test_localized_inprogress_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(
            instrument_id='eproms_add', status='in-progress',
            doc_id='eproms_add')
        mock_qr(instrument_id='epic26', status='in-progress', doc_id='epic26')
        mock_qr(instrument_id='comorb', status='in-progress', doc_id='comorb')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment())
        self.assertEquals(
            set(a_s.instruments_in_progress()), localized_instruments)

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(instrument_id='eproms_add')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertEquals(
            localized_instruments -
            set(a_s.instruments_needing_full_assessment('all')),
            set(['eproms_add']))
        self.assertFalse(a_s.instruments_in_progress())

    def test_metastatic_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_metastatic()
        for i in metastatic_baseline_instruments:
            mock_qr(instrument_id=i)
        mi_qb = QuestionnaireBank.query.filter_by(
            name='metastatic_indefinite').first()
        mock_qr(instrument_id='irondemog', qb=mi_qb)

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "Completed")

        # shouldn't need full or any inprocess
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertFalse(a_s.instruments_in_progress('all'))

    def test_metastatic_due(self):
        # hasn't taken, but still in "Due" period
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "Due")

        # confirm list of expected intruments needing attention
        self.assertEquals(
            metastatic_baseline_instruments,
            set(a_s.instruments_needing_full_assessment()))
        self.assertFalse(a_s.instruments_in_progress())

        # metastatic indefinite should also be 'due'
        self.assertEquals(
            metastatic_indefinite_instruments,
            set(a_s.instruments_needing_full_assessment('indefinite')))
        self.assertFalse(a_s.instruments_in_progress('indefinite'))

    def test_localized_overdue(self):
        # if the user completed something on time, and nothing else
        # is due, should see the thank you message.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        # backdate so the baseline q's have expired
        mock_qr(instrument_id='epic26', status='in-progress')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, "Partially Completed")

        # with all q's expired,
        # instruments_needing_full_assessment and instruments_in_progress
        # should be empty
        self.assertFalse(a_s.instruments_needing_full_assessment())
        self.assertFalse(a_s.instruments_in_progress())

    def test_localized_as_of_date(self):
        # backdating consent beyond expired and the status lookup date
        # within a valid window should show available assessments.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        # backdate so the baseline q's have expired
        mock_qr(instrument_id='epic26', status='in-progress', doc_id='doc-26',
                timestamp=backdate)

        self.test_user = db.session.merge(self.test_user)
        as_of_date = backdate + relativedelta(days=2)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=as_of_date)
        self.assertEquals(a_s.overall_status, "In Progress")

        # with only epic26 started, should see results for both
        # instruments_needing_full_assessment and insturments_in_progress
        self.assertEquals(
            set(['eproms_add', 'comorb']),
            set(a_s.instruments_needing_full_assessment()))
        self.assertEquals(['doc-26'], a_s.instruments_in_progress())

    def test_metastatic_as_of_date(self):
        # backdating consent beyond expired and the status lookup date
        # within a valid window should show available assessments.

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3))
        self.bless_with_basics(setdate=backdate)
        self.mark_metastatic()
        # backdate so the baseline q's have expired
        mock_qr(instrument_id='epic23', status='in-progress', doc_id='doc-23',
                timestamp=backdate)

        self.test_user = db.session.merge(self.test_user)
        as_of_date = backdate + relativedelta(days=2)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=as_of_date)
        self.assertEquals(a_s.overall_status, "In Progress")

        # with only epic26 started, should see results for both
        # instruments_needing_full_assessment and instruments_in_progress
        self.assertEquals(['doc-23'], a_s.instruments_in_progress())
        self.assertTrue(a_s.instruments_needing_full_assessment())

    def test_initial_recur_due(self):

        # backdate so baseline q's have expired, and we within the first
        # recurrence window
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, "Due")

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment()),
            metastatic_3)

    def test_initial_recur_baseline_done(self):
        # backdate to be within the first recurrence window

        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, days=2))
        self.bless_with_basics(setdate=backdate)
        self.mark_metastatic()

        # add baseline QNRs, as if submitted nearly 3 months ago, during
        # baseline window
        backdated = nowish - relativedelta(months=2, days=25)
        baseline = QuestionnaireBank.query.filter_by(
            name='metastatic').one()
        for instrument in metastatic_baseline_instruments:
            mock_qr(instrument, qb=baseline, timestamp=backdated)

        self.test_user = db.session.merge(self.test_user)
        # Check status during baseline window
        a_s_baseline = AssessmentStatus(
            user=self.test_user, as_of_date=backdated)
        self.assertEquals(a_s_baseline.overall_status, "Completed")
        self.assertFalse(a_s_baseline.instruments_needing_full_assessment())

        # Whereas "current" status for the initial recurrence show due.
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, "Due")

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment()),
            metastatic_3)

    def test_secondary_recur_due(self):

        # backdate so baseline q's have expired, and we are within the
        # second recurrence window
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=6, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, "Due")

        # w/ no questionnaires submitted
        # should include all from second recur
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment()),
            metastatic_4)

    def test_batch_lookup(self):
        self.login()
        self.bless_with_basics()
        rv = self.client.get(
            '/api/consent-assessment-status?user_id=1&user_id=2')
        self.assert200(rv)
        self.assertEquals(len(rv.json['status']), 1)
        self.assertEquals(
            rv.json['status'][0]['consents'][0]['assessment_status'],
            'Expired')

    def test_none_org(self):
        # check users w/ none of the above org
        self.test_user.organizations.append(Organization.query.get(0))
        self.login()
        self.bless_with_basics()
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=now)
        self.assertEquals(a_s.overall_status, "Due")

    def test_boundary_overdue(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=-1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, 'Overdue')

    def test_boundary_expired(self):
        "At expired, should be expired"
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, 'Expired')

    def test_boundary_in_progress(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=-1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        for instrument in localized_instruments:
            mock_qr(instrument_id=instrument, status='in-progress')
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, 'In Progress')

    def test_boundary_in_progress_expired(self):
        self.login()
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=3, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()
        for instrument in localized_instruments:
            mock_qr(instrument_id=instrument, status='in-progress')
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, 'Partially Completed')

    def test_all_expired_old_tx(self):
        self.login()
        # backdate outside of baseline window (which uses consent date)
        backdate, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=4, hours=1))
        self.bless_with_basics(setdate=backdate)
        self.mark_localized()

        # provide treatment date outside of all recurrences
        tx_date = datetime(2000, 3, 12, 0, 0, 00, 000000)
        self.add_procedure(code='7', display='Focal therapy',
                           system=ICHOM, setdate=tx_date)

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user, as_of_date=nowish)
        self.assertEquals(a_s.overall_status, 'Expired')



class TestTnthAssessmentStatus(TestQuestionnaireSetup):
    """Tests with Tnth QuestionnaireBanks"""

    eproms_or_tnth = 'tnth'

    def test_no_start_date(self):
        # W/O a biopsy (i.e. event start date), no questionnaries
        self.promote_user(role_name=ROLE.PATIENT)
        # toggle default setup - set biopsy false for test user
        self.login()
        self.test_user = db.session.merge(self.test_user)
        self.test_user.save_observation(
            codeable_concept=CC.BIOPSY, value_quantity=CC.FALSE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status='final', issued=None)
        self.assertFalse(
            QuestionnaireBank.qbs_for_user(
                self.test_user, 'baseline', as_of_date=now))
