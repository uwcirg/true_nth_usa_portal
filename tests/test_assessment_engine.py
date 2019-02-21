"""Unit test module for Assessment Engine API"""
from __future__ import unicode_literals  # isort:skip

from flask_swagger import swagger
from flask_webtest import SessionScope

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier
from portal.models.organization import Organization
from portal.models.questionnaire_bank import (
    QuestionnaireBank,
    QuestionnaireBankQuestionnaire,
)
from portal.models.research_protocol import ResearchProtocol
from portal.models.role import ROLE
from portal.models.user import get_user
from portal.models.user_consent import UserConsent
from tests import TEST_USER_ID, TestCase


class TestAssessmentEngine(TestCase):

    def test_submit_assessment(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200
        response = response.json
        assert response['ok']
        assert response['valid']
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 1
        assert (
            self.test_user.questionnaire_responses[0].encounter.auth_method
            == 'password_authenticated')

    def test_submit_invalid_assessment(self):
        data = {'no_questionnaire_field': True}

        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_invalid_status(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data.pop('identifier')
        data['status'] = 'in-progress'

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_duplicate_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system='https://unique.org', value='abc123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200

        # Submit a second, with the same identifier, expect error
        data2 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data2['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data2)
        assert response.status_code == 409
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 1

        # And a third, with just the id.value changed
        data3 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        identifier.value = 'do-over'
        data3['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data3)
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 2

    def test_invalid_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system=None, value='abc-123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 400

    def test_duplicate_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system='https://unique.org', value='abc123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data),
        )
        assert response.status_code == 200

        # Submit a second, with the same identifier, expect error
        data2 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data2['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data2),
        )
        assert response.status_code == 409
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 1

        # And a third, with just the id.value changed
        data3 = swagger_spec['definitions']['QuestionnaireResponse']['example']
        identifier.value = 'do-over'
        data3['identifier'] = identifier.as_fhir()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data3),
        )
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.questionnaire_responses.count() == 2

    def test_invalid_identifier(self):
        swagger_spec = swagger(self.app)
        identifier = Identifier(system=None, value='abc-123')
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']
        data['identifier'] = identifier.as_fhir()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data),
        )
        assert response.status_code == 400

    def test_submit_assessment_for_qb(self):
        swagger_spec = swagger(self.app)
        data = swagger_spec['definitions']['QuestionnaireResponse']['example']

        rp = ResearchProtocol(name='proto')
        with SessionScope(db):
            db.session.add(rp)
            db.session.commit()
        rp = db.session.merge(rp)
        rp_id = rp.id

        qn = self.add_questionnaire(name='epic26')
        org = Organization(name="testorg")
        org.research_protocols.append(rp)
        with SessionScope(db):
            db.session.add(qn)
            db.session.add(org)
            db.session.commit()

        qn, org = map(db.session.merge, (qn, org))
        qb = QuestionnaireBank(
            name='Test Questionnaire Bank',
            classification='baseline',
            research_protocol_id=rp_id,
            start='{"days": 0}',
            overdue='{"days": 7}',
            expired='{"days": 90}')
        qbq = QuestionnaireBankQuestionnaire(questionnaire=qn, rank=0)
        qb.questionnaires.append(qbq)

        test_user = get_user(TEST_USER_ID)
        test_user.organizations.append(org)
        authored = FHIR_datetime.parse(data['authored'])
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org,
            audit=audit, agreement_url='http://no.com',
            acceptance_date=authored)

        with SessionScope(db):
            db.session.add(qb)
            db.session.add(test_user)
            db.session.add(audit)
            db.session.add(uc)
            db.session.commit()

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=data)
        assert response.status_code == 200
        test_user = get_user(TEST_USER_ID)
        qb = db.session.merge(qb)
        assert test_user.questionnaire_responses.count() == 1
        assert (
            test_user.questionnaire_responses[0].questionnaire_bank_id
            == qb.id)

    def test_update_assessment(self):
        swagger_spec = swagger(self.app)
        completed_qnr = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = (completed_qnr['questionnaire']['reference'].split(
            '/')[-1])

        questions = completed_qnr['group']['question']
        incomplete_questions = []

        # Delete answers for second half of QuestionnaireResponse
        for index, question in enumerate(questions):
            question = question.copy()
            if (index > len(questions) / 2):
                question.pop('answer', [])
            incomplete_questions.append(question)
        in_progress_qnr = completed_qnr.copy()
        in_progress_qnr.update({
            'status': 'in-progress',
            'group': {'question': incomplete_questions},
        })

        self.login()
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.STAFF.value)

        # Upload incomplete QNR
        in_progress_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=in_progress_qnr)
        assert in_progress_response.status_code == 200

        # Update incomplete QNR
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=completed_qnr)
        assert update_qnr_response.status_code == 200
        assert update_qnr_response.json['ok']
        assert update_qnr_response.json['valid']

        updated_qnr_response = self.client.get(
            '/api/patient/assessment?instrument_id={}'.format(instrument_id))
        assert update_qnr_response.status_code == 200
        assert (
            updated_qnr_response.json['entry'][0]['group']
            == completed_qnr['group'])

    def test_no_update_assessment(self):
        swagger_spec = swagger(self.app)
        qnr = swagger_spec['definitions']['QuestionnaireResponse']['example']

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()

        # Upload QNR
        qnr_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=qnr)
        assert qnr_response.status_code == 200

        qnr['identifier']['system'] = 'foo'

        # Attempt to update different QNR; should fail
        update_qnr_response = self.client.put(
            '/api/patient/{}/assessment'.format(TEST_USER_ID), json=qnr)
        assert update_qnr_response.status_code == 404

    def test_assessments_bundle(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[
            -1]

        self.login()
        self.bless_with_basics()
        self.promote_user(role_name=ROLE.STAFF.value)

        upload = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=example_data)
        assert upload.status_code == 200

        response = self.client.get(
            '/api/patient/assessment',
            query_string={'instrument_id': instrument_id})
        response = response.json

        assert response['total'] == len(response['entry'])
        assert (response['entry'][0]['questionnaire']['reference'].endswith(
            instrument_id))

    def test_assessments_csv(self):
        swagger_spec = swagger(self.app)
        example_data = swagger_spec['definitions']['QuestionnaireResponse'][
            'example']
        instrument_id = example_data['questionnaire']['reference'].split('/')[
            -1]

        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        upload_response = self.client.post(
            '/api/patient/{}/assessment'.format(TEST_USER_ID),
            json=example_data)
        assert upload_response.status_code == 200

        download_response = self.client.get(
            '/api/patient/assessment',
            query_string={'format': 'csv', 'instrument_id': instrument_id}
        )
        csv_string = download_response.get_data(as_text=True)
        assert len(csv_string.split("\n")) > 1
        # Todo: use csv module for more robust test
