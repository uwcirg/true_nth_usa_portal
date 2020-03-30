"""Unit test module for terms of use logic"""

from datetime import datetime
import json

from flask_webtest import SessionScope
import pytz

from portal.extensions import db
from portal.models.audit import Audit
from portal.models.notification import Notification, UserNotification
from portal.models.organization import Organization
from portal.models.tou import ToU, update_tous
from tests import TEST_USER_ID

tou_url = 'http://fake-tou.org'


def test_tou_str():
    audit = Audit(
        user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
        comment="Agreed to ToU", context='other')
    tou = ToU(audit=audit, agreement_url=tou_url,
              type='website terms of use')
    results = "{}".format(tou)
    assert tou_url in results


def test_get_tou(client):
    response = client.get('/api/tou')
    assert response.status_code == 200
    assert 'url' in response.json


def test_accept(login, client, test_user):
    login()
    data = {'agreement_url': tou_url}
    response = client.post(
        '/api/tou/accepted',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    tou = ToU.query.one()
    assert tou.agreement_url == tou_url
    assert tou.audit.user_id == TEST_USER_ID


def test_accept_w_org(login, test_user, bless_with_basics, client):
    login()
    bless_with_basics()
    test_user = db.session.merge(test_user)
    org_id = test_user.organizations[0].id
    data = {'agreement_url': tou_url, 'organization_id': org_id}
    response = client.post(
        '/api/tou/accepted',
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    tou = ToU.query.filter(ToU.agreement_url == tou_url).one()
    assert tou.agreement_url == tou_url
    assert tou.audit.user_id == TEST_USER_ID
    assert tou.organization_id == org_id


def test_service_accept(service_user, login, client):
    service_user = db.session.merge(service_user)
    login(user_id=service_user.id)
    data = {'agreement_url': tou_url}
    response = client.post(
        '/api/user/{}/tou/accepted'.format(TEST_USER_ID),
        content_type='application/json',
        data=json.dumps(data))
    assert response.status_code == 200
    tou = ToU.query.one()
    assert tou.agreement_url == tou_url
    assert tou.audit.user_id == TEST_USER_ID


def test_get(login, client, test_user):
    audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
    tou = ToU(audit=audit, agreement_url=tou_url,
              type='website terms of use')
    with SessionScope(db):
        db.session.add(tou)
        db.session.commit()

    login()
    response = client.get('/api/user/{}/tou'.format(TEST_USER_ID))
    doc = response.json
    assert response.status_code == 200
    assert len(doc['tous']) == 1


def test_get_by_type(login, client, test_user):
    timestamp = datetime.utcnow()
    audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                  timestamp=timestamp)
    tou = ToU(audit=audit, agreement_url=tou_url,
              type='privacy policy')
    with SessionScope(db):
        db.session.add(tou)
        db.session.commit()

    login()
    response = client.get('/api/user/{}/tou/privacy-policy'.format(
        TEST_USER_ID))
    assert response.status_code == 200
    # result must be timezone aware isoformat, without microseconds
    tzaware = timestamp.replace(tzinfo=pytz.utc)
    wo_micro = tzaware.replace(microsecond=0)
    assert response.json['accepted'] == wo_micro.isoformat()
    assert response.json['type'] == 'privacy policy'


def test_deactivate_tous(test_user):
    timestamp = datetime.utcnow()

    pptou_audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID,
                        timestamp=timestamp)
    pptou = ToU(audit=pptou_audit, agreement_url=tou_url,
                type='privacy policy')

    wtou_audit = Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID)
    wtou = ToU(audit=wtou_audit, agreement_url=tou_url,
               type='website terms of use')

    with SessionScope(db):
        db.session.add(pptou)
        db.session.add(wtou)
        db.session.commit()
    test_user, pptou, wtou = map(
        db.session.merge, (test_user, pptou, wtou))

    # confirm active
    assert all((pptou.active, wtou.active))

    # test deactivating single type
    test_user.deactivate_tous(test_user, ['privacy policy'])
    assert not pptou.active
    assert wtou.active

    # test deactivating all types
    test_user.deactivate_tous(test_user)
    assert not all((pptou.active, wtou.active))


def test_deactivate_tous_by_org(
        system_user, shallow_org_tree,
        add_user, promote_user, test_user):
    timestamp = datetime.utcnow()

    parent = Organization.query.get(101)
    child = Organization.query.get(1001)  # child of 101
    lonely_leaf = Organization.query.get(102)
    staff = add_user('staff')
    staff_id = staff.id
    promote_user(staff, 'staff')
    staff = db.session.merge(staff)
    staff.organizations.append(parent)
    second_user = add_user('second@foo.bar')
    second_user_id = second_user.id
    promote_user(second_user, 'patient')
    second_user = db.session.merge(second_user)
    second_user.organizations.append(lonely_leaf)
    promote_user(test_user, 'patient')
    test_user = db.session.merge(test_user)
    test_user.organizations.append(child)

    def gentou(user_id, type):
        return ToU(
            audit=Audit(
                user_id=user_id, subject_id=user_id, timestamp=timestamp),
            agreement_url=tou_url, type=type)

    pptou = gentou(TEST_USER_ID, 'privacy policy')
    pptou_2 = gentou(second_user_id, 'privacy policy')
    pptou_staff = gentou(staff_id, 'privacy policy')

    wtou = gentou(TEST_USER_ID, 'website terms of use')
    wtou_2 = gentou(second_user_id, 'website terms of use')
    wtou_staff = gentou(staff_id, 'website terms of use')

    notif_p = Notification(name="priv notif", content="Test Alert!")
    notif_w = Notification(name="web notif", content="Test Alert!")
    tous = (pptou, pptou_2, pptou_staff, wtou, wtou_2, wtou_staff)
    with SessionScope(db):
        db.session.add(notif_p)
        db.session.add(notif_w)
        for t in tous:
            db.session.add(t)
        db.session.commit()

    test_user, second_user, staff, parent = map(
        db.session.merge, (test_user, second_user, staff, parent))
    pptou, pptou_2, pptou_staff, wtou, wtou_2, wtou_staff = map(
        db.session.merge, tous)

    # confirm active
    assert all((pptou.active, pptou_2.active, wtou.active, wtou_2.active))

    # test deactivating single type by org - should miss second user
    update_tous(
        types=['privacy policy'], organization='101',
        notification='priv notif', deactivate=True)
    assert not pptou.active
    assert not pptou_staff.active
    assert all((pptou_2.active, wtou.active, wtou_2.active,
                wtou_staff.active))
    assert UserNotification.query.filter(
        UserNotification.user_id == TEST_USER_ID).count() == 1
    assert UserNotification.query.filter(
        UserNotification.user_id == staff_id).count() == 1
    assert UserNotification.query.filter(
        UserNotification.user_id == second_user_id).count() == 0

    # test limiting to staff on org both staff and test_user belong to
    # only hits staff
    update_tous(
        types=['website terms of use'], organization='101',
        roles=['staff', 'staff_admin'], notification='web notif',
        deactivate=True)
    assert not wtou_staff.active
    assert all((pptou_2.active, wtou.active, wtou_2.active))
    assert UserNotification.query.filter(
        UserNotification.user_id == TEST_USER_ID).count() == 1
    assert UserNotification.query.filter(
        UserNotification.user_id == staff_id).count() == 2
    assert UserNotification.query.filter(
        UserNotification.user_id == second_user_id).count() == 0
