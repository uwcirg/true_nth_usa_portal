"""Auth related view functions"""
from __future__ import unicode_literals  # isort:skip

from abc import ABCMeta, abstractmethod
import base64
from datetime import datetime
import hashlib
import hmac
import json

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.contrib.facebook import make_facebook_blueprint
from flask_dance.contrib.google import make_google_blueprint
from flask_login import logout_user
from flask_user import roles_required
from flask_user.signals import (
    user_changed_password,
    user_logged_in,
    user_registered,
    user_reset_password,
)
import requests
from sqlalchemy.orm.exc import NoResultFound
from ..audit import auditable_event
from ..csrf import csrf
from ..database import db
from ..extensions import oauth
from ..models.auth import AuthProvider, Token
from ..models.client import client_event_dispatch, validate_origin
from ..models.coredata import Coredata
from ..models.encounter import finish_encounter
from ..models.login import login_user
from ..models.role import ROLE
from ..models.user import (
    User,
    add_user,
    current_user,
    get_user_or_abort,
)

auth = Blueprint('auth', __name__)

google_blueprint = make_google_blueprint(
    scope=['profile', 'email'],
    login_url='/login/google/',
)

facebook_blueprint = make_facebook_blueprint(
    scope=['email', 'user_birthday', 'user_gender'],
    login_url='/login/facebook/',
)


class FlaskDanceProvider:
    """base class for flask dance providers

    When a new provider is added to the protal's consumer oauth flow
    a descendent of this class needs to be created to get the user's
    information from the provider after a successful auth
    """
    __metaclass__ = ABCMeta

    def __init__(self, blueprint, token):
        self.blueprint = blueprint
        self.token = token

    @property
    def name(self):
        return self.blueprint.name

    @abstractmethod
    def get_user_info(self):
        """gets user info from the provider

        This function must be overriden in descendant classes
        to return an instance of FlaskProviderUserInfo that is
        filled with user information fetched from the provider
        """
        pass


class MockFlaskDanceProvider(FlaskDanceProvider):
    """creates user info from test data to validate auth logic

    This class should only be used during testing.
    It simply returns the data passed into its constructor in
    get_user_info. This effectively mocks out the get_user_info
    request that's normally sent to a provider after successful oauth
    in non-test environments.
    """

    def __init__(self, provider_name, token, user_info, fail_to_get_user_info):
        blueprint = type(str('MockBlueprint'), (object,), {})
        blueprint.name = provider_name
        super(MockFlaskDanceProvider, self).__init__(
                blueprint,
                token)

        self.user_info = user_info
        self.fail_to_get_user_info = fail_to_get_user_info

    def get_user_info(self):
        """return the user info passed into the constructor

        This effectively mocks out the get_user_info
        request that's normally sent to a provider after successful oauth
        in non-test environments.
        """
        if self.fail_to_get_user_info:
            current_app.logger.debug(
                'MockFlaskDanceProvider failed to get user info'
            )
            return False

        return self.user_info


class GoogleFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Google after successfull auth

    After the user successfully authenticates with Google
    this class fetches the user's info from Google and packages it
    in FlaskDanceProviderUserInfo
    """

    def get_user_info(self):
        """gets user info from Google

        After the user successfully authenticates with Google
        control enters this function which gets the user's info
        from Google and returns an instance of FlaskDanceProviderUserInfo
        """
        resp = self.blueprint.session.get('/oauth2/v2/userinfo')
        if not resp.ok:
            current_app.logger.debug('Failed to fetch user info from Google')
            return False

        google_info = resp.json()

        user_info = FlaskProviderUserInfo()
        user_info.id = google_info['id']
        user_info.first_name = google_info['given_name']
        user_info.last_name = google_info['family_name']
        user_info.email = google_info['email']
        user_info.image_url = google_info['picture']

        # Gender may not be available
        if 'gender' in google_info:
            user_info.gender = google_info['gender']

        # Birthday may not be available
        if 'birthday' in google_info:
            user_info.birthdate = google_info['birthday']

        return user_info


class FacebookFlaskDanceProvider(FlaskDanceProvider):
    """fetches user info from Facebook after successfull auth

    After the user successfully authenticates with Facebook
    this class fetches the user's info from Facebook and packages
    it in FlaskDanceProviderUserInfo
    """

    def get_user_info(self):
        """gets user info from Facebook

        After the user successfully authenticates with Facebook
        control enters this function which gets the user's info from
        Facebook and returns an instance of FlaskDanceProviderUserInfo
        """
        resp = self.blueprint.session.get(
            '/me',
            params={
                'fields':
                    'id,email,birthday,first_name,last_name,gender,picture'})
        if not resp.ok:
            current_app.logger.debug('Failed to fetch user info from Facebook')
            return False

        facebook_info = resp.json()

        user_info = FlaskProviderUserInfo()
        user_info.id = facebook_info['id']
        user_info.first_name = facebook_info['first_name']
        user_info.last_name = facebook_info['last_name']
        user_info.email = facebook_info['email']
        user_info.gender = facebook_info['gender']
        user_info.image_url = facebook_info['picture']['data']['url']
        user_info.birthdate = facebook_info['birthday']

        return user_info


class FlaskProviderUserInfo(object):
    """a common format for user info fetched from providers

    Each provider packages user info a litle differently.
    Google, for example, uses "given_name" and the key for the user's
    first name, and Facebook uses "first_name". To make it easier for
    our code to parse responses in a common function this class provides a
    common format to store the results from each provider.
    """

    def __init__(self):
        self.id = None
        self.first_name = None
        self.last_name = None
        self.email = None
        self.birthdate = None
        self.gender = None
        self.image_url = None


@auth.route('/test/oauth')
def oauth_test_backdoor():
    """unit test backdoor

    API that handles oauth related tasks for unit tests.
    When a test needs to login or test oauth related logic
    this API will likely be used.
    """
    def login_test_user_using_session(user_id):
        assert int(user_id) < 10  # allowed for test users only!
        session['id'] = user_id
        user = current_user()
        login_user(user, 'password_authenticated')
        return next_after_login()

    def login_test_user_with_mock_provider():
        mock_provider = create_mock_provider()
        return login_user_with_provider(request, mock_provider)

    def create_mock_provider():
        user_info = FlaskProviderUserInfo()
        user_info.id = request.args.get('provider_id')
        user_info.first_name = request.args.get('first_name')
        user_info.last_name = request.args.get('last_name')
        user_info.email = request.args.get('email')
        user_info.image_url = request.args.get('image_url')
        user_info.gender = request.args.get('gender')
        user_info.birthday = request.args.get('birthday')

        # If a token is set turn it into a json object
        token = request.args.get('token')
        if token:
            token = json.loads(token)

        mock_provider = MockFlaskDanceProvider(
            request.args.get('provider_name'),
            token,
            user_info,
            request.args.get('fail_to_get_user_info')
        )

        return mock_provider

    if not current_app.config['TESTING']:
        return abort(404)

    # Validate the next arg
    if request.args.get('next'):
        validate_origin(request.args.get('next'))

    # If user_id is set log the user in by updating the session
    user_id = request.args.get('user_id')
    if user_id:
        return login_test_user_using_session(user_id)

    # Otherwise log the user in using the consumer flow
    return login_test_user_with_mock_provider()


@oauth_authorized.connect_via(facebook_blueprint)
def facebook_logged_in(facebook_blueprint, token):
    """successful Facebook login callback

    After successful Facebook authorization control
    returns here. The Facebook blueprint and the oauth bearer
    token are returned and used to log the user into the portal
    """
    facebook_provider = FacebookFlaskDanceProvider(facebook_blueprint, token)
    login_user_with_provider(request, facebook_provider)

    # Disable Flask-Dance's default behavior that saves the oauth token
    return False


@oauth_authorized.connect_via(google_blueprint)
def google_logged_in(google_blueprint, token):
    """successful Google login callback

    After successful Google authorization control
    returns here. The Google blueprint and the oauth bearer
    token are returned and used to log the user into the portal
    """
    google_provider = GoogleFlaskDanceProvider(google_blueprint, token)
    login_user_with_provider(request, google_provider)

    # Disable Flask-Dance's default behavior that saves the oauth token
    return False


def login_user_with_provider(request, provider):
    """provider login

    A common login function for all providers. Once the provider
    calls our server with the user's bearer token, the token
    is wrapped in an instance of FlaskDanceProvider and passed here.
    This function uses it to get more information about the user and,
    if all goes well, log them in.
    """
    store_next_in_session(request, provider)

    if not provider.token:
        current_app.logger.info("User canceled IdP auth - send home")
        return redirect('/')

    # Use the auth token to get user info from the provider
    user_info = provider.get_user_info()
    if not user_info:
        current_app.logger.debug(
            'Failed to get user info at %s',
            provider.name
        )
        return abort(
            500,
            "unable to authorize with provider {}".format(provider.name)
        )

    current_app.logger.debug(
        "Successful authentication at %s", provider.name)

    try:
        # Check to see if the user has logged in
        # with this auth provider at any point in the past
        auth_provider_query = AuthProvider.query.filter_by(
            provider=provider.name,
            provider_id=user_info.id,
        )

        auth_provider = auth_provider_query.one()
    except NoResultFound:
        # If this is the first time the user is logging with this provider
        # create an entry in the provider table. This will be updated with
        # more info below
        auth_provider = AuthProvider(
            provider=provider.name,
            provider_id=user_info.id,
            token=provider.token,
        )

    if auth_provider.user:
        auditable_event(
            "login via {0}".format(provider.name),
            user_id=auth_provider.user_id,
            subject_id=auth_provider.user.id,
            context='login'
        )
    else:
        # This is the user's first time logging in with this provider
        # Check to see if a db entry already exists for the user's email
        # address.
        user_query = User.query.filter_by(email=user_info.email)
        user = user_query.first()

        if user:
            auditable_event(
                "login user via NEW IdP {0}".format(provider.name),
                user_id=user.id,
                subject_id=user.id,
                context='login'
            )
        else:
            # This user has never logged in before.
            # Create a new entry in the user table.
            user = add_user(user_info)

            # Make sure the user is committed
            db.session.commit()

            auditable_event(
                "register new user via {0}".format(provider.name),
                user_id=user.id,
                subject_id=user.id,
                context='account'
            )

        # Associate this user with the new auth provider
        # and prepare to save the changes
        auth_provider.user = user
        db.session.add(auth_provider)

    # Update the user's image in case they're logging in from
    # a different IDP or their image url changed
    auth_provider.user.image_url = user_info.image_url

    # Finally, commit all of our changes
    db.session.commit()

    # Update our session
    session['id'] = auth_provider.user.id
    session['remote_token'] = provider.token

    # Log the user in
    login_user(auth_provider.user, 'password_authenticated')

    return next_after_login()


def store_next_in_session(request, provider):
    """store the 'next' request arg in session

    If the 'next' arg is set on the request store its value
    in the user's session so we can use it to navigate to the
    next page after we're done authenticating
    """
    if request.args.get('next'):
        session['next'] = request.args.get('next')
        validate_origin(session['next'])
        current_app.logger.debug(
            "store-session['next'] <{}> from login/{}".format(
                session['next'], provider.name))


@oauth_error.connect_via(google_blueprint)
@oauth_error.connect_via(facebook_blueprint)
def provider_oauth_error(
    blueprint,
    error,
    error_description=None,
    error_uri=None
):
    """handles outh errors

    If there's an error during provider authentiation
    control returns here. This function attempts to retry
    logging the user in several times before aborting.
    """
    reload_count = session.get('force_reload_count', 0)
    if reload_count > 2:
        current_app.logger.warn(
            "Failed 3 attempts: OAuth error from {name}! "
            "error={error} description={description} uri={uri}"
        ).format(
            name=blueprint.name,
            error=error,
            description=error_description,
            uri=error_uri,
        )
        abort(500, "unable to authorize with provider {}".format(
            blueprint.name))

    session['force_reload_count'] = reload_count + 1
    current_app.logger.info(str(error))
    # Work around for w/ Safari and cookies set to current site only
    # forcing a reload brings the local cookies back into view
    # (they're missing with such a setting on returning from
    # the 3rd party IdP redirect)
    current_app.logger.info("attempting reload on oauth error")
    return render_template('force_reload.html',
                           message=error_description)


@auth.route('/deauthorized', methods=('POST',))
@csrf.exempt
def deauthorized():
    """Callback URL configured on facebook when user deauthorizes

    We receive POST data when a user deauthorizes the session
    between TrueNTH and Facebook.  The POST includes
    a signed_request, decoded as seen below.

    Configuration set on Facebook Developer pages:
      app->settings->advanced->Deauthorize Callback URL

    """
    def base64_url_decode(s):
        """url safe base64 decoding method"""
        padding_factor = (4 - len(s) % 4)
        s += "="*padding_factor
        return base64.b64decode(unicode(s).translate(
            dict(zip(map(ord, '-_'), '+/'))))

    encoded_sig, payload = request.form['signed_request'].split('.')
    sig = base64_url_decode(encoded_sig)
    data = base64_url_decode(payload)

    secret = current_app.config['FB_CONSUMER_SECRET']
    expected_sig = hmac.new(
        secret, msg=payload, digestmod=hashlib.sha256).digest()
    if expected_sig != sig:
        current_app.logger.error("Signed request from FB doesn't match!")
        return jsonify(error='bad signature')

    current_app.logger.debug("data: %s", str(data))
    data = json.loads(data)
    # Should probably remove all tokens obtained during this session
    # for now, just logging the event.
    message = 'User {0} deauthorized TrueNTH from Facebook'.format(
        data['user_id'])
    current_app.logger.info(message)
    return jsonify(message=message)


def flask_user_login_event(app, user, **extra):
    auditable_event("local user login", user_id=user.id, subject_id=user.id,
                    context='login')
    login_user(user, 'password_authenticated')


def flask_user_registered_event(app, user, **extra):
    auditable_event(
        "local user registered", user_id=user.id, subject_id=user.id,
        context='account')


def flask_user_changed_password(app, user, **extra):
    auditable_event(
        "local user changed password", user_id=user.id, subject_id=user.id,
        context='account')
    # As any user, including those not yet registered, may be changing
    # their password via the `forgot password` email loop, remove any
    # special roles left on the account.
    keepers = [
        r for r in user.roles if r.name not in
        current_app.config['PRE_REGISTERED_ROLES']]
    user.update_roles(role_list=keepers, acting_user=user)


# Register functions to receive signals from flask_user
user_logged_in.connect(flask_user_login_event)
user_registered.connect(flask_user_registered_event)
user_changed_password.connect(flask_user_changed_password)
user_reset_password.connect(flask_user_changed_password)


def capture_next_view_function(real_function):
    """closure to hang onto real view function to use after saving 'next'"""
    real_function = real_function

    def capture_next():
        """Alternate view function plugged in to capture 'next' in session

        NB if already logged in - this will bounce user to home, unless
        the user has role write_only, as such users may be logging in
        or registering new accounts, to be merged with the write_only one.

        """
        if (current_user() and not
                current_user().has_role(ROLE.WRITE_ONLY.value)):
            return redirect('/home')

        if request.args.get('next'):
            session['next'] = request.args.get('next')
            validate_origin(session['next'])
            current_app.logger.debug(
                "store-session['next']: <{}> before {}()".format(
                    session['next'], real_function.__name__))
        if request.args.get('suspend_initial_queries'):
            session['suspend_initial_queries'] = request.args.get(
                'suspend_initial_queries')
        return real_function()
    return capture_next


@auth.route('/next-after-login')
def next_after_login():
    """Redirection to appropriate target depending on data and auth status

    Multiple authorization paths in, some needing up front information before
    returning, this attempts to handle such state decisions.  In other words,
    this function represents the state machine to control initial flow.

    When client applications (interventions) request OAuth tokens, we sometimes
    need to postpone the action of authorizing the client while the user logs
    in to TrueNTH.

    After completing authentication with TrueNTH, additional data may need to
    be obtained, such as a TOU agreement.  In such a case, the user will be
    directed to initial_queries, then back here for redirection to the
    appropriate 'next'.

    Implemented as a view method for integration with flask-user config.

    """
    # Without a current_user - can't continue, send back to root for login
    user = current_user()
    if not user:
        current_app.logger.debug("next_after_login: [no user] -> landing")
        return redirect('/')

    # Logged in - take care of pending actions
    if 'challenge_verified_user_id' in session:
        # user has now finished p/w update - clear session variable
        del session['challenge_verified_user_id']

    # Look for an invited user scenario.  Landing here with:
    #   `invited_verified_user_id` set indicates a fresh
    #   registered account for a user who followed an invite email,
    #   or a non-registered account now being promoted to a registered
    #   one (i.e. via the `access_on_verify` role)
    #
    #   `login_as_id` set indicates a fresh registered account during
    #   a login-as session.  In such a case, ignore when the user first
    #   becomes the target login-as user, we need to capture landing here
    #   once a newly registered account has been created.
    #
    # time to promote the invited account.  This also inverts
    # current_user to the invited one once promoted.
    if 'invited_verified_user_id' in session or (
            'login_as_id' in session and
            user.id != int(session['login_as_id'])):
        invited_id = session.get('invited_verified_user_id') or session.get(
            'login_as_id')
        invited_user = User.query.get(invited_id)
        preserve_next_across_sessions = session.get('next')
        logout(prevent_redirect=True, reason='reverting to invited account')
        invited_user.promote_to_registered(user)
        db.session.commit()
        login_user(invited_user, 'password_authenticated')
        if preserve_next_across_sessions:
            session['next'] = preserve_next_across_sessions
        assert (invited_user == current_user())
        assert(not invited_user.has_role(role_name=ROLE.WRITE_ONLY.value))
        user = current_user()
        assert ('invited_verified_user_id' not in session)
        assert ('login_as_id' not in session)

    # Present intial questions (TOU et al) if not already obtained
    # NB - this act may be suspended by request from an external
    # client during patient registration
    if (not session.get('suspend_initial_queries', None) and
            not Coredata().initial_obtained(user)):
        current_app.logger.debug("next_after_login: [need data] -> "
                                 "initial_queries")
        resp = redirect(url_for('portal.initial_queries'))

    # Clients/interventions trying to obtain an OAuth token for protected
    # access need to be put in a pending state, if the user isn't already
    # authenticated with the portal.  It's now time to resume that process;
    # pop the pending state from the session and resume, if found.
    elif 'pending_authorize_args' in session:
        args = session['pending_authorize_args']
        current_app.logger.debug("next_after_login: [resume pending] ->"
                                 "authorize: {}".format(args))
        del session['pending_authorize_args']
        resp = redirect(url_for('auth.authorize', **args))

    # 'next' is typically set on the way in when gathering authentication.
    # It's stored in the session to survive the various redirections needed
    # for external auth, etc.  If found in the session, pop and redirect
    # as defined.
    elif 'next' in session:
        next_url = session['next']
        del session['next']
        current_app.logger.debug("next_after_login: [have session['next']] "
                                 "-> {}".format(next_url))
        if 'suspend_initial_queries' in session:
            del session['suspend_initial_queries']
        resp = redirect(next_url)

    else:
        # No better place to go, send user home
        current_app.logger.debug("next_after_login: [no state] -> home")
        resp = redirect('/home')

    def update_timeout():
        # make cookie max_age outlast the browser session
        max_age = 60 * 60 * 24 * 365 * 5
        # set timeout cookies
        if session.get('login_as_id'):
            if request.cookies.get('SS_TIMEOUT'):
                resp.set_cookie('SS_TIMEOUT_REVERT',
                                request.cookies['SS_TIMEOUT'],
                                max_age=max_age)
            resp.set_cookie('SS_TIMEOUT', '300', max_age=max_age)
        elif request.cookies.get('SS_TIMEOUT_REVERT'):
            resp.set_cookie('SS_TIMEOUT',
                            request.cookies['SS_TIMEOUT_REVERT'],
                            max_age=max_age)
            resp.set_cookie('SS_TIMEOUT_REVERT', '', expires=0)
        else:
            # TODO determine if this line should stay - it seems it
            # would clear a value potentially set on the browser via
            # /settings
            resp.set_cookie('SS_TIMEOUT', '', expires=0)

    ready_for_login_as_timeout = False
    if ready_for_login_as_timeout:
        update_timeout()

    return resp


@auth.route('/login-as/<user_id>')
@roles_required(ROLE.STAFF.value)
@oauth.require_oauth()
def login_as(user_id, auth_method='staff_authenticated'):
    """Provide direct login w/o auth to user account, but only if qualified

    Special individuals may assume the identity of other users, but only
    if the business rules validate.  For example, staff may log in
    as a patient who has a current consent on file for the staff's
    organization.

    If qualified, the current user's session is destroyed and the requested
    user is logged in - passing control to 'next_after_login'

    :param user_id: User (patient) to assume identity of
    :param auth_method: Expected values include 'staff_authenticated' and
      'staff_handed_to_patient', depending on context.

    """
    # said business rules enforced by check_role()
    current_user().check_role('edit', user_id)
    target_user = get_user_or_abort(user_id)

    # Guard against abuse
    if not (target_user.has_role(role_name=ROLE.PATIENT.value) or
            target_user.has_role(role_name=ROLE.PARTNER.value)):
        abort(401, 'not authorized to assume identity of requested user')

    auditable_event("assuming identity of user {}".format(user_id),
                    user_id=current_user().id, subject_id=user_id,
                    context='authentication')

    logout(prevent_redirect=True, reason="forced from login_as")
    session['login_as_id'] = user_id

    if target_user.has_role(role_name=ROLE.WRITE_ONLY.value):
        target_user.mask_email()  # necessary in case registration is attempted
    login_user(target_user, auth_method)
    return next_after_login()


@auth.route('/logout')
def logout(prevent_redirect=False, reason=None):
    """logout view function

    Logs user out by requesting the previously granted permission to
    use authenticated resources be deleted from the OAuth server, and
    clearing the browser session.

    :param prevent_redirect: set only if calling this function during
        another process where redirection after logout is not desired
    :param reason: set only if calling from another process where a driving
        reason should be noted in the audit

    Optional query string parameter timed_out should be set to clarify the
    logout request is the result of a stale session

    """
    user = current_user()
    user_id = user.id if user else None
    timed_out = request.args.get('timed_out', False)

    def delete_facebook_authorization(user_id):
        """Remove OAuth authorization for TrueNTH on logout

        If the user has ever authorized TrueNTH via Facebook,
        tell facebook to delete the authorization now (on logout).

        NB - this isn't standard OAuth behavior, users only expect to
        authorize TrueNTH one time to use their Facebook
        authentication.

        """
        ap = AuthProvider.query.filter_by(
            provider='facebook', user_id=user_id).first()
        if ap:
            headers = {
                'Authorization': 'Bearer {0}'.format(session['remote_token'])}
            url = "https://graph.facebook.com/{0}/permissions".\
                format(ap.provider_id)
            requests.delete(url, headers=headers)

    if user_id:
        event = 'logout' if not timed_out else 'logout due to timeout'
        if reason:
            event = ':'.join((event, reason))
        auditable_event(
            event, user_id=user_id, subject_id=user_id, context='login')
        # delete_facebook_authorization()  #Not using at this time

    logout_user()
    session.clear()

    if user:
        client_event_dispatch(event="logout", user=user, timed_out=timed_out)
        finish_encounter(user)
    db.session.commit()
    if prevent_redirect:
        return
    return redirect('/' if not timed_out else '/?timed_out=1')




@auth.route('/oauth/token-status')
@oauth.require_oauth()
def token_status():
    """Return remaining valid time and other info for oauth token

    Endpoint for clients needing to double check status on a token.
    Returns essentially the same JSON obtained from the /oauth/token
    call, with `expires_in` updated to show remaining seconds.

    ---
    tags:
      - OAuth
    operationId: token_status
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: token_status
          required:
            - access_token
            - token_type
            - expires_in
            - refresh_token
            - scope
            - scopes
          properties:
            access_token:
              type: string
              description:
                The access token to include in the Authorization header
                for protected API use.
            token_type:
              type: string
              description: Type of access token, always 'Bearer'
            expires_in:
              type: integer
              format: int64
              description:
                Number of seconds for which the access token will
                remain valid
            refresh_token:
              type: string
              description:
                Use to refresh an access token, in place of the
                authorizion token.
            scope:
              type: string
              description: The authorized scope.
            scopes:
              type: string
              description: Deprecated version of `scope` containing identical data.

    """
    authorization = request.headers.get('Authorization')
    if not authorization:
        abort(401, "Authorization header required")
    token_type, access_token = authorization.split()
    token = Token.query.filter_by(access_token=access_token).first()
    if not token:
        abort(404, "token not found")
    expires_in = token.expires - datetime.utcnow()
    return jsonify(
        access_token=access_token,
        refresh_token=token.refresh_token, token_type=token_type,
        expires_in=expires_in.seconds,
        scope=token._scopes, scopes=token._scopes)


@auth.route('/oauth/errors', methods=('GET', 'POST'))
@csrf.exempt
def oauth_errors():
    """Redirect target for oauth errors

    Shouldn't be called directly, this endpoint is the redirect target
    when something goes wrong during authorization code requests
    ---
    tags:
      - OAuth
    operationId: oauth_errors
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: error_response
          required:
            - error
          properties:
            error:
              type: string
              description: Known details of error situation.

    """
    current_app.logger.warn(request.args.get('error'))
    return jsonify(error=request.args.get('error')), 400


@auth.route('/oauth/token', methods=('GET', 'POST'))
@csrf.exempt
@oauth.token_handler
def access_token():
    """Exchange authorization code for access token

    OAuth client libraries must POST the authorization code obtained
    from /oauth/authorize in exchange for a Bearer Access Token.
    ---
    tags:
      - OAuth
    operationId: access_token
    parameters:
      - name: client_id
        in: formData
        description:
          Client's unique identifier, obtained during registration
        required: true
        type: string
      - name: client_secret
        in: formData
        description:
          Client's secret, obtained during registration
        required: true
        type: string
      - name: code
        in: formData
        description:
          The authorization code obtained from /oauth/authorize
        required: true
        type: string
      - name: grant_type
        in: formData
        description:
          Type of OAuth authorization requested.  Use "authorization_code"
        required: true
        type: string
      - name: redirect_uri
        in: formData
        description:
          Intervention's target URI for call back.
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description: successful operation
        schema:
          id: access_token
          required:
            - access_token
            - token_type
            - expires_in
            - refresh_token
            - scope
          properties:
            access_token:
              type: string
              description:
                The access token to include in the Authorization header
                for protected API use.
            token_type:
              type: string
              description: Type of access token, always 'Bearer'
            expires_in:
              type: integer
              format: int64
              description:
                Number of seconds for which the access token will
                remain valid
            refresh_token:
              type: string
              description:
                Use to refresh an access token, in place of the
                authorizion token.
            scope:
              type: string
              description: The authorized scope.

    """
    for field in request.form:
        if '\0' in request.form[field]:
            abort(400, "invalid {} string".format(field))
    return None


@auth.route('/oauth/authorize', methods=('GET', 'POST'))
@csrf.exempt
@oauth.authorize_handler
def authorize(*args, **kwargs):
    """Authorize the client to access TrueNTH resources

    For OAuth 2.0, the resource owner communicates their desire
    to grant the client (intervention) access to their data on
    the server (TrueNTH).

    For ease of use, this decision has been hardwired to "allow access"
    on TrueNTH. Making a GET request to this endpoint is still
    the required initial step in the OAuth 2.0 Authorization Code
    Grant (http://tools.ietf.org/html/rfc6749#section-4.1), likely
    handled by the OAuth 2.0 library used by the client.
    ---
    tags:
      - OAuth
    operationId: oauth_authorize
    parameters:
      - name: response_type
        in: query
        description:
          Type of OAuth authorization requested.  Use "code"
        required: true
        type: string
      - name: client_id
        in: query
        description:
          Client's unique identifier, obtained during registration
        required: true
        type: string
      - name: redirect_uri
        in: query
        description:
          Intervention's target URI for call back, which may include
          its own query string parameters for use by the intervention
          on call back.  Must be urlencoded as per the OAuth specification
          (https://tools.ietf.org/html/rfc6749#section-4.1.1)
        required: true
        type: string
      - name: scope
        in: query
        description:
          Extent of authorization requested.  At this time, only 'email'
          is supported.  See https://tools.ietf.org/html/rfc6749#section-3.3
        required: true
        type: string
      - name: display_html
        in: query
        description: Additional HTML to customize registration
        required: false
        type: string
      - name: suspend_initial_queries
        in: query
        description:
         include with true value to suspend the gathering of initial
         data such as roles, terms of use, organization, demographics,
         etc.
        type: string
    produces:
      - application/json
    responses:
      302:
        description:
          redirect to requested redirect_uri with a valid
          authorization code. NB - this is not the bearer
          token needed for API access, but the code to be
          exchanged for such an access token. In the
          event of an error, redirection will target /oauth/errors
          of TrueNTH.

    """
    # Interventions may include additional text to display as a way
    # to "customize registration".  Store in session for display in
    # templates.
    if 'display_html' in request.args:
        session['display_html'] = request.args.get('display_html')
        current_app.logger.debug("display_html:" +
                                 request.args.get('display_html'))

    suspend_initial_queries = request.args.get('suspend_initial_queries')
    if suspend_initial_queries:
        session['suspend_initial_queries'] = True
        current_app.logger.debug("/oauth/authorize told to suspend_initial_queries")

    user = current_user()
    if not user:
        # Entry point when intervention is requesting OAuth token, but
        # the user has yet to authenticate via FB or otherwise.  Need
        # to retain the request, and replay after TrueNTH login
        # has completed.
        current_app.logger.debug(
            'Postponing oauth client authorization till user '
            'authenticates with CS: %s', str(request.args))
        session['pending_authorize_args'] = request.args

        return redirect('/')
    # See "hardwired" note in docstring above
    return True
