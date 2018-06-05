"""Extensions used at application level

Generally the objects instantiated here are needed for imports
throughout the system, but require factory pattern initialization
once the flask `app` comes to life.

Defined here to break the circular dependencies.  See `app.py` for
additional configuration of most objects defined herein.

"""
# Flask-OAuthLib provides OAuth between the Portal and the Interventions
from functools import wraps

# Flask-Authomatic provides OAuth between the Portal and upstream
# identity providers such as Facebook
from authomatic import Authomatic
from authomatic.providers import oauth2
from database import db
from flask import abort, request
# Babel is used for i18n
from flask_babel import Babel
# Flask-Mail is used for email communication
from flask_mail import Mail
from flask_oauthlib.provider import OAuth2Provider
# ReCaptcha is used for form verification
from flask_recaptcha import ReCaptcha
# Flask-Session provides server side sessions
from flask_session import Session
# Flask-User
from flask_user import SQLAlchemyAdapter, UserManager

from .csrf import csrf
from .models.login import login_user
from .models.user import User, current_user

db_adapter = SQLAlchemyAdapter(db, User)
user_manager = UserManager(db_adapter)




class OAuthOrAlternateAuth(OAuth2Provider):
    """Specialize OAuth2Provider with alternate authorization"""

    def __init__(self, app=None):
        super(OAuthOrAlternateAuth, self).__init__(app)

    def require_oauth(self, *scopes):
        """Specialze the superclass decorator with alternates

        This method is intended to be in lock step with the
        super class, with the following two exceptions:

        1. if actively "TESTING", skip oauth and return
           the function, effectively undecorated.

        2. if the user appears to be locally logged in (i.e. browser
           session cookie with a valid user.id),
           return the effecively undecorated function.

        """
        def wrapper(eff):
            """preserve name and docstrings on 'eff'

            see: http://stackoverflow.com/questions/308999/what-does-functools-wraps-do

            """
            @csrf.exempt
            @wraps(eff)
            def decorated(*args, **kwargs):  # pragma: no cover
                """decorate the 'eff' function"""
                # TESTING backdoor
                if self.app.config.get('TESTING'):
                    return eff(*args, **kwargs)
                # Local login backdoor
                if current_user():
                    return eff(*args, **kwargs)

                # Superclass method follows
                # all MODs clearly marked
                for func in self._before_request_funcs:
                    func()

                if hasattr(request, 'oauth') and request.oauth:
                    # Start MOD
                    # Need to log oauth user in for flask-user roles, etc.
                    login_user(request.oauth.user, 'password_authenticated')
                    # End MOD
                    return eff(*args, **kwargs)

                valid, req = self.verify_request(scopes)

                for func in self._after_request_funcs:
                    valid, req = func(valid, req)

                if not valid:
                    if self._invalid_response:
                        return self._invalid_response(req)
                    return abort(401)
                request.oauth = req
                # Start MOD
                # Need to log oauth user in for flask-user roles, etc.
                login_user(request.oauth.user, 'password_authenticated')
                # End MOD
                return eff(*args, **kwargs)
            return decorated
        return wrapper

oauth = OAuthOrAlternateAuth()



class _delay_init(object):
    """We can't initialize authomatic till the app config is ready"""

    def __init__(self):
        self._authomatic = None

    @property
    def authomatic(self):
        return self._authomatic

    def init_app(self, app):
        if self._authomatic:
            return
        self._authomatic = Authomatic(
            config={
                'facebook': {
                    'class_': oauth2.Facebook,
                    'consumer_key': app.config['FB_CONSUMER_KEY'],
                    'consumer_secret': app.config['FB_CONSUMER_SECRET'],
                    'scope': ['public_profile', 'email'],
                },
                'google': {
                    'class_': oauth2.Google,
                    'consumer_key': app.config['GOOGLE_CONSUMER_KEY'],
                    'consumer_secret': app.config['GOOGLE_CONSUMER_SECRET'],
                    'scope': ['profile', 'email'],
                },
            },
            secret=app.config['SECRET_KEY'],
            debug=True,
            logger=app.logger
        )


authomatic = _delay_init()


mail = Mail()

session = Session()

babel = Babel()

recaptcha = ReCaptcha()
