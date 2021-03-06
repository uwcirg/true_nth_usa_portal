from http.cookies import SimpleCookie

from flask_webtest import SessionScope

from portal.database import db
from portal.models.intervention import INTERVENTION, UserIntervention
from tests import TEST_USER_ID


def test_default_timeout(test_user_login, client):
    # Default timeout should be 30 mins
    response = client.get('/next-after-login', follow_redirects=False)
    cookies = SimpleCookie()
    [cookies.load(item[1]) for item in response.headers
        if item[0] == 'Set-Cookie']
    assert int(cookies['SS_INACTIVITY_TIMEOUT'].value) == 30 * 60


def test_SR_timeout(test_user_login, client):
    # SR users get 1 hour
    ui = UserIntervention(
        user_id=TEST_USER_ID,
        intervention_id=INTERVENTION.SEXUAL_RECOVERY.id)
    with SessionScope(db):
        db.session.add(ui)
        db.session.commit()

    response = client.get('/next-after-login', follow_redirects=False)
    cookies = SimpleCookie()
    [cookies.load(item[1]) for item in response.headers
        if item[0] == 'Set-Cookie']
    assert int(cookies['SS_INACTIVITY_TIMEOUT'].value) == 60 * 60


def test_kiosk_mode(app, test_user_login, client):
    # Mock scenario where system is configured with unique timeout
    system_timeout = '299'
    client.set_cookie(
        app.config['SERVER_NAME'], 'SS_TIMEOUT', system_timeout)
    response = client.get(
            '/next-after-login', follow_redirects=False)
    cookies = SimpleCookie()
    [cookies.load(item[1]) for item in response.headers
     if item[0] == 'Set-Cookie']
    assert cookies['SS_INACTIVITY_TIMEOUT'].value == system_timeout
