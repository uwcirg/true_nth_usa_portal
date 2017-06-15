"""Configuration"""
import os
import redis
from flask_script import Server


def best_sql_url():
    """Return compliant sql url from available enviornment variables"""
    env = os.environ
    if 'PGDATABASE' in env:
        return (
            'postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}/{PGDATABASE}'.format(
                PGUSER=env.get('PGUSER'), PGPASSWORD=env.get('PGPASSWORD'),
                PGHOST=env.get('PGHOST', 'localhost'),
                PGDATABASE=env.get('PGDATABASE')))
    elif 'SQLALCHEMY_DATABASE_URI' in env:
        return env.get('SQLALCHEMY_DATABASE_URI')
    else:
        return env.get(
            'DATABASE_URL',
            'postgresql://test_user:4tests_only@localhost/portal_unit_tests'
        )


class BaseConfig(object):
    """Base configuration - override in subclasses"""

    SERVER_NAME = os.environ.get(
        'SERVER_NAME',
        'localhost'
    )

    # Allow Heroku env vars to override most defaults
    # NB: The value of REDIS_URL may change at any point
    REDIS_URL = os.environ.get(
        'REDIS_URL',
        'redis://localhost:6379'
    )

    ANONYMOUS_USER_ACCOUNT = True
    CELERY_BROKER_URL = os.environ.get(
        'CELERY_BROKER_URL',
        REDIS_URL + '/0'
    )
    REQUEST_CACHE_URL = os.environ.get(
        'REQUEST_CACHE_URL',
        REDIS_URL + '/0'
    )
    CELERY_IMPORTS = ('portal.tasks', )
    CELERY_RESULT_BACKEND = 'redis'
    DEBUG = False
    DEFAULT_MAIL_SENDER = 'dontreply@truenth-demo.cirg.washington.edu'
    LOG_FOLDER = os.environ.get('LOG_FOLDER', None)
    LOG_LEVEL = 'DEBUG'

    MAIL_USERNAME = 'portal@truenth-demo.cirg.washington.edu'
    MAIL_DEFAULT_SENDER = '"TrueNTH" <noreply@truenth-demo.cirg.washington.edu>'
    CONTACT_SENDTO_EMAIL = MAIL_USERNAME
    ERROR_SENDTO_EMAIL = MAIL_USERNAME
    OAUTH2_PROVIDER_TOKEN_EXPIRES_IN = 4 * 60 * 60  # units: seconds
    SS_TIMEOUT = 60 * 60  # seconds for session cookie, reset on ping
    PERMANENT_SESSION_LIFETIME = SS_TIMEOUT
    PIWIK_DOMAINS = ""
    PIWIK_SITEID = 0
    PORTAL_STYLESHEET = 'css/portal.css'
    PROJECT = "portal"
    SHOW_EXPLORE = True
    SHOW_PROFILE_MACROS = ['ethnicity', 'race']
    SHOW_PUBLIC_TERMS = True
    SHOW_WELCOME = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = best_sql_url()
    SECRET_KEY = 'override this secret key'
    SESSION_PERMANENT = True
    SESSION_TYPE = 'redis'

    SESSION_REDIS_URL = os.environ.get(
        'SESSION_REDIS_URL',
        REDIS_URL + '/0'
    )

    # Todo: create issue @ fengsp/flask-session
    # config values aren't typically objects...
    SESSION_REDIS = redis.from_url(SESSION_REDIS_URL)

    TESTING = False
    USER_APP_NAME = 'TrueNTH'  # used by email templates
    USER_AFTER_LOGIN_ENDPOINT = 'auth.next_after_login'
    USER_AFTER_CONFIRM_ENDPOINT = USER_AFTER_LOGIN_ENDPOINT
    USER_ENABLE_USERNAME = False  # using email as username
    USER_ENABLE_CHANGE_USERNAME = False  # prereq for disabling username
    USER_ENABLE_CONFIRM_EMAIL = False  # don't force email conf on new accounts

    STAFF_BULK_DATA_ACCESS = True
    PATIENT_LIST_ADDL_FIELDS = [] # 'status', 'reports'

    FB_CONSUMER_KEY = os.environ.get('FB_CONSUMER_KEY', '')
    FB_CONSUMER_SECRET = os.environ.get('FB_CONSUMER_SECRET', '')
    GOOGLE_CONSUMER_KEY = os.environ.get('GOOGLE_CONSUMER_KEY', '')
    GOOGLE_CONSUMER_SECRET = os.environ.get('GOOGLE_CONSUMER_SECRET', '')

    DEFAULT_LOCALE = 'en_US'
    FILE_UPLOAD_DIR = 'uploads'
    LR_ORIGIN = 'https://stg-lr7.us.truenth.org'
    LR_GROUP = 20147

    SYSTEM_TYPE = 'development'

    SMARTLING_USER_ID = os.environ.get('SMARTLING_USER_ID', None)
    SMARTLING_USER_SECRET = os.environ.get('SMARTLING_USER_SECRET', None)
    SMARTLING_PROJECT_ID = os.environ.get('SMARTLING_PROJECT_ID', None)

class DefaultConfig(BaseConfig):
    """Default configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False

class TestConfig(BaseConfig):
    """Testing configuration - used by unit tests"""
    TESTING = True
    SERVER_NAME = 'localhost:5005'
    LIVESERVER_PORT = 5005
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_TEST_URI',
        "postgresql://test_user:4tests_only@localhost/portal_unit_tests")

    WTF_CSRF_ENABLED = False
    FILE_UPLOAD_DIR = 'test_uploads'
