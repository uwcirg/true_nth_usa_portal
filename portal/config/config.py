"""Configuration"""
import os
import redis


SITE_CFG = 'site.cfg'


def best_sql_url():
    """Return compliant sql url from available enviornment variables"""
    env = os.environ
    if 'PGDATABASE' in env:
        return (
            'postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}/{PGDATABASE}'.format(
                PGUSER=env.get('PGUSER'), PGPASSWORD=env.get('PGPASSWORD'),
                PGHOST=env.get('PGHOST', 'localhost'),
                PGDATABASE=env.get('PGDATABASE')))


class BaseConfig(object):
    """Base configuration - override in subclasses"""
    TESTING = False

    SERVER_NAME = os.environ.get(
        'SERVER_NAME',
        'localhost'
    )

    # Allow Heroku env vars to override most defaults
    # NB: The value of REDIS_URL may change at any point
    REDIS_URL = os.environ.get(
        'REDIS_URL',
        'redis://localhost:6379/0'
    )

    ANONYMOUS_USER_ACCOUNT = True
    BROKER_URL = os.environ.get(
        'BROKER_URL',
        REDIS_URL
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        'CELERY_RESULT_BACKEND',
        REDIS_URL
    )
    REQUEST_CACHE_URL = os.environ.get(
        'REQUEST_CACHE_URL',
        REDIS_URL
    )
    REQUEST_CACHE_EXPIRE = 10

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL')
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', str(TESTING)).lower() == 'true'
    CONTACT_SENDTO_EMAIL = os.environ.get('CONTACT_SENDTO_EMAIL')
    ERROR_SENDTO_EMAIL = os.environ.get('ERROR_SENDTO_EMAIL')

    CELERY_IMPORTS = ('portal.tasks', )
    DEBUG = False
    DOGPILE_CACHE_BACKEND = 'dogpile.cache.redis'
    DOGPILE_CACHE_REGIONS = [('hourly', 3600)]
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60  # 1 hour, in seconds

    LOG_FOLDER = os.environ.get('LOG_FOLDER')
    LOG_LEVEL = 'DEBUG'

    OAUTH2_PROVIDER_TOKEN_EXPIRES_IN = 4 * 60 * 60  # units: seconds
    SS_TIMEOUT = 60 * 60  # seconds for session cookie, reset on ping
    PERMANENT_SESSION_LIFETIME = SS_TIMEOUT
    PIWIK_DOMAINS = ""
    PIWIK_SITEID = 0
    PORTAL_STYLESHEET = 'css/portal.css'
    PRE_REGISTERED_ROLES = ['access_on_verify', 'write_only', 'promote_without_identity_challenge']
    PROJECT = "portal"
    SHOW_EXPLORE = True
    SHOW_PROFILE_MACROS = ['ethnicity', 'race']
    SHOW_PUBLIC_TERMS = True
    SHOW_WELCOME = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = best_sql_url()
    SESSION_PERMANENT = True
    SESSION_TYPE = 'redis'

    SESSION_REDIS_URL = os.environ.get(
        'SESSION_REDIS_URL',
        REDIS_URL
    )

    # Todo: create issue @ fengsp/flask-session
    # config values aren't typically objects...
    SESSION_REDIS = redis.from_url(SESSION_REDIS_URL)

    USER_APP_NAME = 'TrueNTH'  # used by email templates
    USER_AFTER_LOGIN_ENDPOINT = 'auth.next_after_login'
    USER_AFTER_CONFIRM_ENDPOINT = USER_AFTER_LOGIN_ENDPOINT
    USER_ENABLE_USERNAME = False  # using email as username
    USER_ENABLE_CHANGE_USERNAME = False  # prereq for disabling username
    USER_ENABLE_CONFIRM_EMAIL = False  # don't force email conf on new accounts
    USER_SHOW_USERNAME_EMAIL_DOES_NOT_EXIST = False

    STAFF_BULK_DATA_ACCESS = True
    PATIENT_LIST_ADDL_FIELDS = []  # 'status', 'reports'

    FB_CONSUMER_KEY = os.environ.get('FB_CONSUMER_KEY')
    FB_CONSUMER_SECRET = os.environ.get('FB_CONSUMER_SECRET')
    GOOGLE_CONSUMER_KEY = os.environ.get('GOOGLE_CONSUMER_KEY')
    GOOGLE_CONSUMER_SECRET = os.environ.get('GOOGLE_CONSUMER_SECRET')

    DEFAULT_LOCALE = 'en_US'
    FILE_UPLOAD_DIR = 'uploads'

    LR_ORIGIN = os.environ.get('LR_ORIGIN', 'https://stg-lr7.us.truenth.org')
    LR_GROUP = os.environ.get('LR_GROUP', 20145)
    LR_FOLDER_ST = os.environ.get('LR_FOLDER_ST', 35564)

    SYSTEM_TYPE = os.environ.get('SYSTEM_TYPE', 'development')

    # Only set cookies over "secure" channels (HTTPS) for non-dev deployments
    SESSION_COOKIE_SECURE = SYSTEM_TYPE.lower() != 'development'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'http')

    BABEL_CONFIG_FILENAME = 'gil.babel.cfg'

    SMARTLING_USER_ID = os.environ.get('SMARTLING_USER_ID')
    SMARTLING_USER_SECRET = os.environ.get('SMARTLING_USER_SECRET')
    SMARTLING_PROJECT_ID = os.environ.get('SMARTLING_PROJECT_ID')

    RECAPTCHA_ENABLED = True
    RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
    SECRET_KEY = os.environ.get('SECRET_KEY')

    TREATMENT_OPTIONS = [
    ('373818007', 'http://snomed.info/sct'),
    ('424313000', 'http://snomed.info/sct'),
    ('26294005', 'http://snomed.info/sct'),
    ('26294005-nns', 'http://snomed.info/sct'),
    ('33195004', 'http://snomed.info/sct'),
    ('228748004', 'http://snomed.info/sct'),
    ('707266006', 'http://snomed.info/sct'),
    ('999999999', 'http://snomed.info/sct')]


class DefaultConfig(BaseConfig):
    """Default configuration"""
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    SQLALCHEMY_ECHO = False


class TestConfig(BaseConfig):
    """Testing configuration - used by unit tests"""
    TESTING = True
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', str(TESTING)).lower() == 'true'
    SERVER_NAME = 'localhost:5005'
    LIVESERVER_PORT = 5005
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_TEST_URI',
        "postgresql://test_user:4tests_only@localhost/portal_unit_tests")

    WTF_CSRF_ENABLED = False
    FILE_UPLOAD_DIR = 'test_uploads'
    SECRET_KEY = 'testing key'
