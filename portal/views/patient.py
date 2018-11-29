"""Patient API - implements patient specific views such as patient search

NB - this is not to be confused with 'patients', which defines views
for staff

"""
import json

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import and_
from werkzeug.exceptions import Unauthorized

from ..audit import auditable_event
from ..database import db
from ..extensions import oauth
from ..models.fhir import bundle_results
from ..models.identifier import Identifier, UserIdentifier
from ..models.qb_timeline import QBT, update_users_QBT
from ..models.reference import Reference
from ..models.role import ROLE
from ..models.user import User, current_user, get_user_or_abort
from .crossdomain import crossdomain
from .demographics import demographics

patient_api = Blueprint('patient_api', __name__)


@patient_api.route('/api/patient/')
@crossdomain()
@oauth.require_oauth()
def patient_search():
    """Looks up patient(s) from given parameters, returns FHIR Patient bundle

    Takes key=value pairs to look up.  Email, identifier searches supported.

    Example searches:
        /api/patient?email=username@server.com
        /api/patient?identifier=http://us.truenth.org/identity-codes/external-study-id|123-45-678

    Identifier search pattern:
        ?identifier=<system>|<value>

    Deleted users and users for which the authenticated user does not have
    permission to view will NOT be included in the results.

    NB - the results are restricted to users with the patient role.  It is
    therefore possible to get no results from this and still see a unique email
    collision from existing non-patient users.

    NB - currently out of FHIR DSTU2 spec by default.  Include query string
    parameter ``patch_dstu2=True`` to properly return a FHIR bundle resource
    (https://www.hl7.org/fhir/DSTU2/bundle.html) naming the ``total`` matches
    and references to all matching patients.  With ``patch_dstu2=True``, the
    total will be zero if no matches are found, whereas the default (old,
    non-compliant) behavior is to return a 404 when no match is found.
    Please consider using the ``patch_dstu2=True`` parameter, as this will
    become the default behavior in the future.

    Returns a FHIR bundle resource (https://www.hl7.org/fhir/DSTU2/bundle.html)
    formatted in JSON for all matching valid, accessible patients, with
    ``patch_dstu2=True`` set (preferred).  Default returns single patient on a
    match, 404 on no match, and 400 for multiple as it's not supported.

    ---
    tags:
      - Patient
    operationId: patient_search
    produces:
      - application/json
    parameters:
      - name: search_parameters
        in: query
        description:
            Search parameters, such as `email` or `identifier`.  For
            identifier, URL-encode the `system` and `value` using '|' (pipe)
            delimiter, i.e. `api/patient/?identifier=http://fake.org/id|12a7`
        required: true
        type: string
      - name: patch_dstu2
        in: query
        description: whether or not to return DSTU2 compliant bundle
        required: false
        type: boolean
        default: false
    responses:
      200:
        description:
          Returns FHIR patient resource (http://www.hl7.org/fhir/patient.html)
          in JSON if a match is found.  Otherwise responds with a 404 status
          code.
      401:
        description:
          if missing valid OAuth token
      404:
        description:
          if there is no match found, or the user lacks permission to look
          up details on the match.
    security:
      - ServiceToken: []

    """
    if not request.args.items():
        abort(400, "missing search criteria")

    def parse_identifier_params(v):
        # Supporting pipe delimiter and legacy dict parameters
        if '|' in v:
            system, value = v.split('|')
        else:
            try:
                ident_dict = json.loads(v)
                system = ident_dict.get('system')
                value = ident_dict.get('value')
            except ValueError:
                abort(400, "Ill formed identifier parameter")
        return system, value

    query = User.query.filter(User.deleted_id.is_(None))
    for k, v in request.args.items():
        if k == 'email':
            query = query.filter(User.email == v)
        elif k == 'identifier':
            system, value = parse_identifier_params(v)
            if not (system and value):
                abort(400, "need 'system' and 'value' to look up identifier")

            query = query.join(UserIdentifier).join(
                Identifier).filter(and_(
                    UserIdentifier.identifier_id == Identifier.id,
                    Identifier.system == system,
                    Identifier._value == value))
        elif k == 'patch_dstu2':
            # not search criteria, but valid
            continue
        else:
            abort(400, "can't search on '{}' at this time".format(k))

    # Validate permissions to see every requested user - omitting those w/o
    patients = []
    for user in query:
        try:
            current_user().check_role(permission='view', other_id=user.id)
            if user.has_role(ROLE.PATIENT.value):
                patients.append(
                    {'resource': Reference.patient(user.id).as_fhir()})
        except Unauthorized:
            # Mask unauthorized as a not-found.  Don't want unauthed users
            # farming information - i.e. don't add to results
            auditable_event("looking up users with inadequate permission",
                            user_id=current_user().id, subject_id=user.id,
                            context='authentication')

    if request.args.get('patch_dstu2', False):
        link = {"rel": "self", "href": request.url}
        return jsonify(bundle_results(elements=patients, links=[link]))
    else:
        # Emulate old results
        if len(patients) == 0:
            abort(404)
        if len(patients) > 1:
            abort(400, "multiple results found, include `patch_dstu2=True`")

        ref = Reference.parse(patients[0]['resource'])
        return demographics(patient_id=ref.id)


@patient_api.route('/api/patient/<int:patient_id>/deceased', methods=('POST',))
@crossdomain()
@oauth.require_oauth()
def post_patient_deceased(patient_id):
    """POST deceased datetime or status for a patient

    This convenience API wraps the ability to set a patient's
    deceased status and deceased date time - generally the /api/demographics
    API should be preferred.

    ---
    operationId: deceased
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: deceased_details
          properties:
            deceasedBoolean:
              type: string
              description:
                true or false.  Implicitly true with deceasedDateTime value
            deceasedDateTime:
              type: string
              description: valid FHIR datetime string defining time of death
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't function, such as a false
          deceasedBoolean AND a deceasedDateTime value.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json or set(request.json.keys()).isdisjoint(
            {'deceasedDateTime', 'deceasedBoolean'}):
        abort(400, "Requires deceasedDateTime or deceasedBoolean in JSON")

    patient.update_deceased(request.json)
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))


@patient_api.route(
    '/api/patient/<int:patient_id>/birthdate', methods=('POST',))
@patient_api.route(
    '/api/patient/<int:patient_id>/birthDate', methods=('POST',))
@oauth.require_oauth()
def post_patient_dob(patient_id):
    """POST date of birth for a patient

    This convenience API wraps the ability to set a patient's birthDate.
    Generally the /api/demographics API should be preferred.

    ---
    tags:
      - Patient
    produces:
      - application/json
    parameters:
      - name: patient_id
        in: path
        description: TrueNTH user ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: dob_details
          properties:
            birthDate:
              type: string
              description: valid FHIR date string defining date of birth
    responses:
      200:
        description:
          Returns updated [FHIR patient
          resource](http://www.hl7.org/fhir/patient.html) in JSON.
      400:
        description:
          if given parameters don't validate
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to edit requested patient
    security:
      - ServiceToken: []

    """
    current_user().check_role(permission='edit', other_id=patient_id)
    patient = get_user_or_abort(patient_id)
    if not request.json or 'birthDate' not in request.json:
        abort(400, "Requires `birthDate` in JSON")

    patient.update_birthdate(request.json)
    db.session.commit()
    auditable_event("updated demographics on user {0} from input {1}".format(
        patient.id, json.dumps(request.json)), user_id=current_user().id,
        subject_id=patient.id, context='user')

    return jsonify(patient.as_fhir(include_empties=False))


@patient_api.route('/api/patient/<int:patient_id>/timeline')
@oauth.require_oauth()
def patient_timeline(patient_id):
    from ..date_tools import FHIR_datetime
    from ..models.questionnaire_bank import QuestionnaireBank, QBD, visit_name
    from ..models.recur import Recur

    current_user().check_role(permission='view', other_id=patient_id)
    patient = get_user_or_abort(patient_id)

    update_users_QBT(patient, invalidate_existing=True)

    results = []
    for qbt in QBT.query.filter(QBT.user_id == patient_id).order_by(QBT.at):
        # build qbd for visit name
        qb = QuestionnaireBank.query.get(qbt.qb_id)
        recur = Recur.query.get(qbt.qb_recur_id) if qbt.qb_recur_id else None
        qbd = QBD(
            relative_start=qbt.at, questionnaire_bank=qb,
            iteration=qbt.qb_iteration, recur=recur)
        results.append({
            'status': qbt.status,
            'at': FHIR_datetime.as_fhir(qbt.at),
            'visit': visit_name(qbd)})

    return jsonify(timeline=results)
