"""Module to test assessment_status"""
from datetime import datetime, timedelta
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.assessment_status import AssessmentStatus
from portal.models.assessment_status import invalidate_assessment_status_cache
from portal.models.encounter import Encounter
from portal.models.organization import Organization
from portal.models.questionnaire import Questionnaire
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_bank import QuestionnaireBankQuestionnaire
from portal.models.recur import Recur
from portal.models.fhir import QuestionnaireResponse
from tests import TestCase, TEST_USER_ID


def mock_qr(user_id, instrument_id, status='completed'):
    today = datetime.utcnow()
    qr_document = {
        "questionnaire": {
            "display": "Additional questions",
            "reference":
            "https://{}/api/questionnaires/{}".format(
                'SERVER_NAME', instrument_id)
        }
    }
    enc = Encounter(status='planned', auth_method='url_authenticated',
                    user_id=TEST_USER_ID, start_time=datetime.utcnow())
    with SessionScope(db):
        db.session.add(enc)
        db.session.commit()
    enc = db.session.merge(enc)
    qr = QuestionnaireResponse(
        subject_id=TEST_USER_ID,
        status=status,
        authored=today,
        document=qr_document,
        encounter_id=enc.id)
    with SessionScope(db):
        db.session.add(qr)
        db.session.commit()
    invalidate_assessment_status_cache(user_id)


localized_instruments = set(['eproms_add', 'epic26', 'comorb'])
metastatic_baseline_instruments = set([
    'eortc', 'ironmisc', 'factfpsi', 'epic26', 'prems'])
metastatic_indefinite_instruments = set(['irondemog'])
metastatic_recurring_instruments = set([
    'eortc', 'hpfs', 'prems', 'epic26'])


def mock_questionnairebanks():
    # Define test Orgs and QuestionnaireBanks for each group
    localized_org = Organization(name='localized')
    metastatic_org = Organization(name='metastatic')

    # Recurring assessments every 3 months up to 24 months, then every
    # 6 months prems alternate with epic26 - start with prems
    initial_recur = Recur(
        days_to_start=90, days_in_cycle=90,
        days_till_termination=720)
    initial_recur_prems = Recur(
        days_to_start=90, days_in_cycle=180,
        days_till_termination=720)
    initial_recur_epic26 = Recur(
        days_to_start=180, days_in_cycle=180,
        days_till_termination=720)
    every_six_thereafter = Recur(
        days_to_start=720, days_in_cycle=180)
    every_six_thereafter_prems = Recur(
        days_to_start=720, days_in_cycle=360)
    every_six_thereafter_epic26 = Recur(
        days_to_start=900, days_in_cycle=360)

    with SessionScope(db):
        for name in (localized_instruments.union(*(
                metastatic_baseline_instruments,
                metastatic_indefinite_instruments,
                metastatic_recurring_instruments))):
            db.session.add(Questionnaire(name=name))
        db.session.add(localized_org)
        db.session.add(metastatic_org)
        db.session.add(initial_recur)
        db.session.add(initial_recur_prems)
        db.session.add(initial_recur_epic26)
        db.session.add(every_six_thereafter)
        db.session.add(every_six_thereafter_prems)
        db.session.add(every_six_thereafter_epic26)
        db.session.commit()
    localized_org, metastatic_org = map(
        db.session.merge, (localized_org, metastatic_org))
    localized_org_id = localized_org.id
    metastatic_org_id = metastatic_org.id
    initial_recur = db.session.merge(initial_recur)
    initial_recur_prems = db.session.merge(initial_recur_prems)
    initial_recur_epic26 = db.session.merge(initial_recur_epic26)
    every_six_thereafter = db.session.merge(every_six_thereafter)
    every_six_thereafter_prems = db.session.merge(every_six_thereafter_prems)
    every_six_thereafter_epic26 = db.session.merge(every_six_thereafter_epic26)

    # Localized baseline
    l_qb = QuestionnaireBank(
        name='localized',
        classification='baseline',
        organization_id=localized_org_id)
    for rank, instrument in enumerate(localized_instruments):
        q = Questionnaire.query.filter_by(name=instrument).one()
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=7, days_till_overdue=90,
            rank=rank)
        l_qb.questionnaires.append(qbq)

    # Metastatic baseline
    mb_qb = QuestionnaireBank(
        name='metastatic',
        classification='baseline',
        organization_id=metastatic_org_id)
    for rank, instrument in enumerate(metastatic_baseline_instruments):
        q = Questionnaire.query.filter_by(name=instrument).one()
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=1, days_till_overdue=30,
            rank=rank)
        mb_qb.questionnaires.append(qbq)

    # Metastatic indefinite
    mi_qb = QuestionnaireBank(
        name='metastatic_indefinite',
        classification='indefinite',
        organization_id=metastatic_org_id)
    for rank, instrument in enumerate(metastatic_indefinite_instruments):
        q = Questionnaire.query.filter_by(name=instrument).one()
        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=1, days_till_overdue=3000,
            rank=rank)
        mi_qb.questionnaires.append(qbq)

    # Metastatic recurring
    mr_qb = QuestionnaireBank(
        name='metastatic_recurring',
        classification='recurring',
        organization_id=metastatic_org_id)
    for rank, instrument in enumerate(metastatic_recurring_instruments):
        q = Questionnaire.query.filter_by(name=instrument).one()
        if instrument == 'prems':
            recurs = [initial_recur_prems, every_six_thereafter_prems]
        elif instrument == 'epic26':
            recurs = [initial_recur_epic26, every_six_thereafter_epic26]
        else:
            recurs = [initial_recur, every_six_thereafter]

        qbq = QuestionnaireBankQuestionnaire(
            questionnaire=q, days_till_due=1, days_till_overdue=30,
            rank=rank, recurs=recurs)
        mr_qb.questionnaires.append(qbq)

    with SessionScope(db):
        db.session.add(l_qb)
        db.session.add(mb_qb)
        db.session.add(mi_qb)
        db.session.add(mr_qb)
        db.session.commit()


class TestQuestionnaireSetup(TestCase):
    "Base for test classes needing mock questionnaire setup"

    def setUp(self):
        super(TestQuestionnaireSetup, self).setUp()
        mock_questionnairebanks()
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
    def test_enrolled_in_metastatic(self):
        """metastatic should include baseline and indefinite"""
        self.bless_with_basics()
        self.mark_metastatic()
        user = db.session.merge(self.test_user)

        a_s = AssessmentStatus(user=user)
        self.assertTrue(a_s.enrolled_in_classification('baseline'))
        self.assertTrue(a_s.enrolled_in_classification('indefinite'))

    def test_enrolled_in_localized(self):
        """localized should include baseline but not indefinite"""
        self.bless_with_basics()
        self.mark_localized()
        user = db.session.merge(self.test_user)

        a_s = AssessmentStatus(user=user)
        self.assertTrue(a_s.enrolled_in_classification('baseline'))
        self.assertFalse(a_s.enrolled_in_classification('indefinite'))

    def test_localized_using_org(self):
        self.bless_with_basics()
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)

        # confirm appropriate instruments
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment('baseline')),
            localized_instruments)

        # check due date access
        for questionnaire in a_s.questionnaire_data.baseline():
            self.assertTrue(questionnaire.get('by_date') > datetime.utcnow())

        self.assertFalse(a_s.instruments_in_progress('baseline'))
        self.assertFalse(a_s.instruments_in_progress('all'))

    def test_localized_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Completed")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

    def test_localized_inprogress_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertEquals(
            set(a_s.instruments_in_progress('baseline')),
            localized_instruments)

    def test_localized_in_process(self):
        # User finished one, time remains for other
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')

        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "In Progress")

        # confirm appropriate instruments
        self.assertEquals(
            localized_instruments -
            set(a_s.instruments_needing_full_assessment('all')),
            set(['eproms_add']))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

    def test_metastatic_on_time(self):
        # User finished both on time
        self.bless_with_basics()  # pick up a consent, etc.
        mock_qr(user_id=TEST_USER_ID, instrument_id='eortc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='ironmisc')
        mock_qr(user_id=TEST_USER_ID, instrument_id='factfpsi')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='prems')
        mock_qr(user_id=TEST_USER_ID, instrument_id='irondemog')

        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Completed")

        # shouldn't need full or any inprocess
        self.assertFalse(a_s.instruments_needing_full_assessment('all'))
        self.assertFalse(a_s.instruments_in_progress('all'))

    def test_metastatic_due(self):
        # hasn't taken, but still in "Due" period
        self.bless_with_basics()  # pick up a consent, etc.
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Due")

        # confirm list of expected intruments needing attention
        a_s.instruments_needing_full_assessment('baseline')
        self.assertEquals(
            metastatic_baseline_instruments,
            set(a_s.instruments_needing_full_assessment('baseline')))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

        # metastatic indefinite should also be 'due'
        self.assertEquals(
            metastatic_indefinite_instruments,
            set(a_s.instruments_needing_full_assessment('indefinite')))
        self.assertFalse(a_s.instruments_in_progress('indefinite'))

    def test_metastatic_overdue(self):
        # if the user completed something on time, and nothing else
        # is due, should see the thankyou message.

        # backdate so the baseline q's have expired
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        self.bless_with_basics(backdate=timedelta(days=31))
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Partially Completed")

        # with all q's from baseline expired,
        # instruments_needing_full_assessment and insturments_in_progress
        # should be empty
        self.assertFalse(a_s.instruments_needing_full_assessment('baseline'))
        self.assertFalse(a_s.instruments_in_progress('baseline'))

        # mock completing the indefinite QB and expect to see 'thank you'
        mock_qr(user_id=TEST_USER_ID, instrument_id='irondemog')
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertTrue(a_s.enrolled_in_classification('indefinite'))
        self.assertFalse(a_s.instruments_needing_full_assessment('indefinite'))
        self.assertFalse(a_s.instruments_in_progress('indefinite'))

    def test_initial_recur_due(self):

        # backdate so baseline q's have expired, and we within the first
        # recurrance window
        self.bless_with_basics(backdate=timedelta(days=90))
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Expired")

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment('recurring')),
            set(['eortc', 'hpfs', 'prems']))

    def test_secondary_recur_due(self):

        # backdate so baseline q's have expired, and we within the
        # second recurrance window
        self.bless_with_basics(backdate=timedelta(days=180))
        self.mark_metastatic()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Expired")

        # in the initial window w/ no questionnaires submitted
        # should include all from initial recur
        self.assertEquals(
            set(a_s.instruments_needing_full_assessment('recurring')),
            set(['eortc', 'hpfs', 'epic26']))

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
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, "Due")

    def test_boundry_overdue(self):
        "At days_till_overdue, should still be overdue"
        self.login()
        self.bless_with_basics(backdate=timedelta(days=89, hours=23))
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, 'Overdue')

    def test_boundry_expired(self):
        "At days_till_overdue +1, should be expired"
        self.login()
        self.bless_with_basics(backdate=timedelta(days=91))
        self.mark_localized()
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, 'Expired')

    def test_boundry_in_progress(self):
        self.login()
        self.bless_with_basics(backdate=timedelta(days=89, hours=23))
        self.mark_localized()
        for instrument in localized_instruments:
            mock_qr(
                user_id=TEST_USER_ID, instrument_id=instrument,
                status='in-progress')
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, 'In Progress')

    def test_boundry_in_progress_expired(self):
        self.login()
        self.bless_with_basics(backdate=timedelta(days=91))
        self.mark_localized()
        for instrument in localized_instruments:
            mock_qr(
                user_id=TEST_USER_ID, instrument_id=instrument,
                status='in-progress')
        self.test_user = db.session.merge(self.test_user)
        a_s = AssessmentStatus(user=self.test_user)
        self.assertEquals(a_s.overall_status, 'Partially Completed')
