# test plugin
# https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
import pytest
from portal.database import db
from portal.factories.app import create_app
from portal.factories.celery import create_celery

from portal.config.config import TestConfig
from flask_webtest import SessionScope
from portal.models.client import Client
from portal.models.clinical_constants import CC, add_static_concepts
from portal.models.intervention import INTERVENTION, add_static_interventions
from portal.models.organization import (
    Organization,
    OrgTree,
    add_static_organization,
)
from portal.models.qb_timeline import invalidate_users_QBT
from portal.models.relationship import add_static_relationships
from portal.models.role import ROLE, Role, add_static_roles
from portal.models.user import User, UserRoles, get_user


def pytest_addoption(parser):
    parser.addoption(
        "--include-ui-testing",
        action="store_true",
        default=False,
        help="run selenium ui tests",
    )


#def setUp():
#    db.drop_all()
#    db.create_all()
#    with SessionScope(db):
#        add_static_concepts(only_quick=True)
#        add_static_interventions()
#        add_static_organization()
#        add_static_questionnaire_bank()
#        add_static_relationships()
#        add_static_roles()
#        db.session.commit()


@pytest.fixture(scope="session")
def app(request):
    """Fixture to use as parameter in any test needing app access

    NB - use of pytest-flask ``client`` fixture is more common

    """
    app_ = create_app()
    ctx = app_.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return app_


@pytest.fixture(scope="session")
def app_logger(app):
    """fixture for functions requiring current_app.logger"""
    return app.logger


@pytest.fixture(scope='session')
def initialized_db(app):
    """Create database schema"""
    db.create_all()


@pytest.fixture(scope='session')
def celery_worker_parameters():
    # type: () -> Mapping[str, Any]
    """Redefined like fixture from celery.contrib.pytest.py as instructed

    Specifically, we need to extend the default queues so the celery worker
    will process tasks given to either queue.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.worker.WorkController`.
    """
    return {
        'queues': ('celery', 'low_priority'),
        'perform_ping_check': False}


@pytest.fixture(scope='session')
def celery_app(app):
    """Fixture to use as parameter in any test needing celery"""
    celery = create_celery(app)

    # bring celery_worker fixture into scope
    from celery.contrib.testing import tasks  # NOQA

    return celery


@pytest.fixture(scope="session")
def test_user(app):
    db.drop_all()
    db.create_all()
    DEFAULT_PASSWORD = 'fakePa$$'

    TEST_USERNAME = 'test@example.com'
    FIRST_NAME = '✓'
    LAST_NAME = 'Last'
    IMAGE_URL = 'http://examle.com/photo.jpg'

    test_user = User(
        username=TEST_USERNAME, first_name=FIRST_NAME,
        last_name=LAST_NAME, image_url=IMAGE_URL, 
        password=DEFAULT_PASSWORD)
    with SessionScope(db):
        #User.query.filter_by(username=TEST_USERNAME).delete()
        db.session.add(test_user)
        db.session.commit()
    test_user = db.session.merge(test_user)
    invalidate_users_QBT(test_user.id)

    yield test_user


@pytest.fixture
def add_service_user(test_user):
    def add_service_user(sponsor=None):
        add_static_concepts(only_quick=True)
        add_static_interventions()
        add_static_relationships()
        add_static_roles()
        db.session.commit()
        if not sponsor:
            sponsor = test_user
        if sponsor not in db.session:
            sponsor = db.session.merge(sponsor)
        service_user = sponsor.add_service_account()
        with SessionScope(db):
            db.session.add(service_user)
            db.session.commit()
    
        return db.session.merge(service_user)
    return add_service_user


@pytest.fixture
def login(app, client):
    def login(user_id=1):
        add_static_organization()
        follow_redirects = True

        app.config.from_object(TestConfig)
        
        oauth_info = {'user_id': user_id}
    
        return client.get(
                'test/oauth',
                query_string=oauth_info,
                follow_redirects=follow_redirects
        )

    return login
    db.session.remove()
    db.engine.dispose()


#@pytest.fixture(scope="session")
#def promote_user():
#    user = None
#    role_name = ROLE.APPLICATION_DEVELOPER.value
#    if not user:
#        user = test_user
#
#
#@pytest.fixture(scope="session")
#def add_client(promote_user):
#    client_id = 'test_client'
#    client = Client(
#        client_id=client_id, _redirect_uris='http://localhost',
#        client_secret='tc_secret', user_id=TEST_USER_ID)
#    with SessionScope(db):
#        db.session.add(client)
#        db.session.commit()
#    return db.session.merge(client)
#
#
#@pytest.fixture(scope="session")
#def login():
#    TEST_USER_ID = 1
#    oauth_info = None
#    follow_redirects = True
#    
#    if not oauth_info:
#        oauth_info = {'user_id': TEST_USER_ID}
#
#    return client.get(
#            'test/oauth',
#            query_string=oauth_info,
#            follow_redirects=follow_redirects
#    )
#
#
#@pytest.fixture(scope="session")
#def add_service_user():
#    sponser = None
#
#    if not sponsor:
#        sponsor = self.test_user
#    if sponsor not in db.session:
#        sponsor = db.session.merge(sponsor)
#    service_user = sponsor.add_service_account()
#    with SessionScope(db):
#        db.session.add(service_user)
#        db.session.commit()
#    return db.session.merge(service_user)
