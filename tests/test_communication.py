"""Unit test module for communication"""
from datetime import timedelta
from flask_webtest import SessionScope

from portal.database import db
from portal.models.communication import Communication
from portal.models.communication_request import CommunicationRequest
from portal.models.identifier import Identifier
from portal.models.intervention import Intervention
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.role import ROLE
from portal.system_uri import TRUENTH_CR_NAME
from portal.tasks import update_patient_loop
from tests import TEST_USER_ID, TEST_USERNAME
from tests.test_assessment_status import TestQuestionnaireSetup, mock_qr


def mock_communication_request(
        questionnaire_bank_name, notify_days,
        communication_request_name=None):
    qb = QuestionnaireBank.query.filter_by(name=questionnaire_bank_name).one()
    cr = CommunicationRequest(
        status='active',
        questionnaire_bank=qb,
        notify_days_after_event=notify_days)
    if communication_request_name:
        ident = Identifier(
            system=TRUENTH_CR_NAME, value=communication_request_name)
        cr.identifiers.append(ident)
    with SessionScope(db):
        db.session.add(cr)
        db.session.commit()
    return db.session.merge(cr)


class TestCommunication(TestQuestionnaireSetup):
    # by inheriting from TestAssessmentStatus, pick up the
    # same mocking done for interacting with QuestionnaireBanks et al

    def test_empty(self):
        # Base test system shouldn't generate any messages
        count_b4 = Communication.query.count()
        self.assertFalse(count_b4)

        update_patient_loop(update_cache=False, queue_messages=True)
        count_after = Communication.query.count()
        self.assertEquals(count_b4, count_after)

    def test_nearready_message(self):
        # At 13 days with all work in-progress, shouldn't generate message

        mock_communication_request('localized', 14)

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=13))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_ready_message(self):
        # At 14 days with all work in-progress, should generate message

        mock_communication_request(
            'localized', 14, "Symptom Tracker | 3 Mo Reminder (1)")

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26',
                status='in-progress')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb',
                status='in-progress')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertEquals(expected.user_id, TEST_USER_ID)

    def test_noworkdone_message(self):
        # At 14 days with no work started, should generate message

        mock_communication_request('localized', 14)

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertEquals(expected.user_id, TEST_USER_ID)

    def test_done_message(self):
        # At 14 days with all work done, should not generate message

        mock_communication_request('localized', 14)

        # Fake a user associated with localized org
        # and mark all baseline questionnaires as in-progress
        self.bless_with_basics(backdate=timedelta(days=14))
        self.promote_user(role_name=ROLE.PATIENT)
        self.mark_localized()
        mock_qr(user_id=TEST_USER_ID, instrument_id='eproms_add')
        mock_qr(user_id=TEST_USER_ID, instrument_id='epic26')
        mock_qr(user_id=TEST_USER_ID, instrument_id='comorb')

        update_patient_loop(update_cache=False, queue_messages=True)
        expected = Communication.query.first()
        self.assertFalse(expected)

    def test_create_message(self):

        cr = mock_communication_request(
            'localized', 14, "Symptom Tracker | 3 Mo Reminder (1)")
        comm = Communication(user_id=TEST_USER_ID, communication_request=cr)

        # in testing, link_url isn't set:
        st = Intervention.query.filter_by(name='self_management').one()
        if not st.link_url:
            st.link_url = 'https://stg-sm.cirg.washington.edu'

        comm.generate_and_send()

        # Testing config doesn't send email unless MAIL_SUPPRESS_SEND
        # is set false.  Confirm persisted data from the fake send
        # looks good.

        self.assertTrue(comm.message)
        self.assertEquals(comm.message.recipients, TEST_USERNAME)
        self.assertEquals(comm.status, 'completed')
