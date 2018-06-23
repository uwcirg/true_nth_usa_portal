"""Test module for patient specific APIs"""
from datetime import datetime
import json
import sys

from flask_webtest import SessionScope
import pytest

from portal.date_tools import FHIR_datetime
from portal.extensions import db
from portal.models.audit import Audit
from portal.models.identifier import Identifier, UserIdentifier
from portal.models.role import ROLE
from portal.models.user import User
from tests import TEST_USER_ID, TEST_USERNAME, TestCase


if sys.version_info.major > 2:
    pytest.skip(msg="not yet ported to python3", allow_module_level=True)
class TestPatient(TestCase):

    def test_email_search(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        self.assert200(rv)
        self.assertTrue(rv.json['resourceType'] == 'Patient')

    def test_email_search_non_patient(self):
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format(TEST_USERNAME),
            follow_redirects=True)
        # Known patient but w/o patient role should 404
        self.assert404(rv)

    def test_inadequate_perms(self):
        dummy = self.add_user(username='dummy@example.com')
        self.promote_user(user=dummy, role_name=ROLE.PATIENT.value)
        self.login()
        rv = self.client.get(
            '/api/patient?email={}'.format('dummy@example.com'),
            follow_redirects=True)
        # w/o permission, should see a 404 not a 401 on search
        self.assert404(rv)

    def test_ident_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        rv = self.client.get(
            '/api/patient?identifier={}'.format(json.dumps(ident.as_fhir())),
            follow_redirects=True)
        self.assert200(rv)

    def test_ident_nomatch_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        # modify the system to mis match
        id_str = json.dumps(ident.as_fhir()).replace(
            "example.com", "wrong-system.com")
        rv = self.client.get(
            '/api/patient?identifier={}'.format(id_str),
            follow_redirects=True)
        self.assert404(rv)

    def test_ill_formed_ident_search(self):
        ident = Identifier(system='http://example.com', value='testy')
        ui = UserIdentifier(identifier=ident, user_id=TEST_USER_ID)
        with SessionScope(db):
            db.session.add(ident)
            db.session.add(ui)
            db.session.commit()
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        ident = db.session.merge(ident)
        rv = self.client.get(
            '/api/patient?identifier=system"http://example.com",value="testy"',
            follow_redirects=True)
        self.assert400(rv)

    def test_birthDate(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        data = {'birthDate': '1976-07-04'}
        rv = self.client.post(
            '/api/patient/{}/birthDate'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)
        user = User.query.get(TEST_USER_ID)
        self.assertTrue(user.birthdate)
        self.assertEqual(user.birthdate.strftime("%Y-%m-%d"), "1976-07-04")

    def test_deceased(self):
        self.promote_user(role_name=ROLE.PATIENT.value)
        self.login()
        now = FHIR_datetime.as_fhir(datetime.utcnow())
        data = {'deceasedDateTime': now}
        rv = self.client.post(
            '/api/patient/{}/deceased'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        self.assert200(rv)
        user = User.query.get(TEST_USER_ID)
        self.assertTrue(user.deceased)

    def test_deceased_undead(self):
        """POST should allow reversal if already deceased"""
        self.promote_user(role_name=ROLE.PATIENT.value)
        d_audit = Audit(
            user_id=TEST_USER_ID, subject_id=TEST_USER_ID, context='user',
            comment="time of death for user {}".format(TEST_USER_ID))
        with SessionScope(db):
            db.session.add(d_audit)
            db.session.commit()
        self.test_user, d_audit = map(db.session.merge, (self.test_user, d_audit))
        self.test_user.deceased = d_audit
        self.login()
        data = {'deceasedBoolean': False}
        rv = self.client.post(
            '/api/patient/{}/deceased'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))
        self.assertTrue(rv.status_code, 200)
        patient = User.query.get(TEST_USER_ID)
        self.assertFalse(patient.deceased)
