"""Unit test module for user consent"""
from datetime import datetime
import json

from dateutil import parser
from flask import current_app
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.organization import Organization
from portal.models.user_consent import UserConsent
from tests import TEST_USER_ID, TestCase

class TestUserConsent(TestCase):
    url = 'http://fake.com?arg=critical'

    def test_content_options(self):
        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        self.shallow_org_tree()
        org1, _ = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        uc = UserConsent(
            user_id=TEST_USER_ID, organization=org1,
            audit=audit, agreement_url='http://no.com')
        uc.include_in_reports = True
        with SessionScope(db):
            db.session.add(uc)
            db.session.commit()

        uc = UserConsent.query.first()
        assert uc.include_in_reports
        assert not uc.staff_editable
        assert not uc.send_reminders

    def test_user_consent(self):
        self.shallow_org_tree()
        org1, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc1 = UserConsent(
            organization_id=org1.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc2 = UserConsent(
            organization_id=org2.id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc1.staff_editable = True
        uc1.send_reminders = False
        uc2.staff_editable = True
        uc2.send_reminders = False
        uc2.status = 'suspended'
        with SessionScope(db):
            db.session.add(uc1)
            db.session.add(uc2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        response = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        assert response.status_code == 200
        assert len(response.json['consent_agreements']) == 2
        assert 'send_reminders' not in response.json['consent_agreements'][0]
        assert 'staff_editable' in response.json['consent_agreements'][0]
        assert response.json['consent_agreements'][0]['status'] == 'consented'
        assert response.json['consent_agreements'][1]['status'] == 'suspended'

    def test_post_user_consent(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': False}

        self.login()
        response = self.client.post(
                              '/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id, org1.id
        assert consent.staff_editable
        assert not consent.send_reminders

    def test_post_user_consent_dates(self):
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        acceptance_date = "2007-10-30"
        data = {'organization_id': org1.id,
                'agreement_url': self.url,
                'acceptance_date': acceptance_date}

        self.login()
        response = self.client.post(
                              '/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert consent.acceptance_date == parser.parse(acceptance_date)
        assert consent.audit.comment ==\
            "Consent agreement {} signed".format(consent.id)
        assert (datetime.utcnow() - consent.audit.timestamp).seconds < 30

    def test_post_replace_user_consent(self):
        """second consent for same user,org should replace existing"""
        self.shallow_org_tree()
        org1 = Organization.query.filter(Organization.id > 0).first()
        data = {'organization_id': org1.id, 'agreement_url': self.url,
                'staff_editable': True, 'send_reminders': True}

        self.login()
        response = self.client.post(
                              '/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        assert response.status_code == 200
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert consent.staff_editable
        assert consent.send_reminders
        assert consent.status == 'consented'

        # modify flags & repost - should have new values and only one
        data['staff_editable'] = False
        data['send_reminders'] = False
        data['status'] = 'suspended'
        response = self.client.post(
                              '/api/user/{}/consent'.format(TEST_USER_ID),
                              content_type='application/json',
                              data=json.dumps(data))
        assert response.status_code == 200
        assert self.test_user.valid_consents.count() == 1
        consent = self.test_user.valid_consents[0]
        assert consent.organization_id == org1.id
        assert not consent.staff_editable
        assert not consent.send_reminders
        assert consent.status == 'suspended'

        dc = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                         organization_id=org1.id,
                                         status='deleted').first()
        assert dc.deleted_id

    def test_delete_user_consent(self):
        self.shallow_org_tree()
        org1, org2 = [org for org in Organization.query.filter(
            Organization.id > 0).limit(2)]
        org1_id, org2_id = org1.id, org2.id
        data = {'organization_id': org1_id}

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc1 = UserConsent(
            organization_id=org1_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        uc2 = UserConsent(
            organization_id=org2_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        with SessionScope(db):
            db.session.add(uc1)
            db.session.add(uc2)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 2
        self.login()

        response = self.client.delete(
                                '/api/user/{}/consent'.format(TEST_USER_ID),
                                content_type='application/json',
                                data=json.dumps(data))
        assert response.status_code == 200
        assert self.test_user.valid_consents.count() == 1
        assert self.test_user.valid_consents[0].organization_id == org2_id

        # We no longer omit deleted consent rows, but rather, include
        # their audit data.
        response = self.client.get('/api/user/{}/consent'.format(TEST_USER_ID))
        assert 'deleted' in json.dumps(response.json)

        # confirm deleted status
        dc = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                         organization_id=org1_id).first()
        assert dc.status == 'deleted'

    def test_withdraw_user_consent(self):
        self.shallow_org_tree()
        org = Organization.query.filter(Organization.id > 0).first()
        org_id = org.id

        audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
        uc = UserConsent(
            organization_id=org_id, user_id=TEST_USER_ID,
            agreement_url=self.url, audit=audit)
        with SessionScope(db):
            db.session.add(uc)
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        assert self.test_user.valid_consents.count() == 1

        data = {'organization_id': org_id}
        self.login()
        resp = self.client.post('/api/user/{}/consent/'
                                'withdraw'.format(TEST_USER_ID),
                                content_type='application/json',
                                data=json.dumps(data))
        assert resp.status_code == 200

        # check that old consent is marked as deleted
        old_consent = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                                  organization_id=org_id,
                                                  status='deleted').first()
        assert old_consent.deleted_id

        # check new withdrawn consent
        new_consent = UserConsent.query.filter_by(user_id=TEST_USER_ID,
                                                  organization_id=org_id,
                                                  status='suspended').first()
        assert old_consent.agreement_url == new_consent.agreement_url
        assert new_consent.staff_editable == \
               (not current_app.config.get('GIL'))
        assert not new_consent.send_reminders
