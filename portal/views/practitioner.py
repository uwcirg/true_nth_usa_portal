"""Practitioner API view functions"""
from flask import abort, jsonify, Blueprint, request
from flask import render_template, current_app, url_for
from flask_user import roles_required
import json
from sqlalchemy import and_

from ..audit import auditable_event
from ..database import db
from ..date_tools import FHIR_datetime
from ..extensions import oauth
from ..models.identifier import Identifier
from ..models.practitioner import Practitioner, PractitionerIdentifier
from ..models.reference import MissingReference
from ..models.role import ROLE
from ..models.user import current_user
from .portal import check_int


practitioner_api = Blueprint('practitioner_api', __name__, url_prefix='/api')


@practitioner_api.route('/practitioner')
@oauth.require_oauth()
def practitioner_search():
    """Obtain a bundle (list) of all matching practitioners

    Filter search on key=value pairs.

    Example search:
        /api/practitioner?first_name=Indiana&last_name=Jones

    Or to lookup by identifier, include system and value:
        /api/practitioner?system=http%3A%2F%2Fpcctc.org%2F&value=146-31

    Returns a JSON FHIR bundle of practitioners as per given search terms.
    Without any search terms, returns all practitioners known to the system.
    If search terms are provided but no matching practitioners are found,
    a 404 is returned.

    ---
    operationId: practitioner_search
    tags:
      - Practitioner
    parameters:
      - name: search_parameters
        in: query
        description:
            Search parameters (`first_name`, `last_name`)
        required: false
        type: string
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a FHIR bundle of [practitioner
          resources](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      400:
        description:
          if invalid search param keys are used
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient
      404:
        description:
          if no practitioners found for given search parameters

    """
    query = Practitioner.query
    system, value = None, None
    for k, v in request.args.items():
        if (k == 'system') and v:
            system = v
        elif (k == 'value') and v:
            value = v
        elif k in ('first_name', 'last_name'):
            if v:
                d = {k: v}
                query = query.filter_by(**d)
        else:
            abort(400, "only `first_name`, `last_name`, and `system`/`value` "
                  "search filters are available at this time")

    if system or value:
        if not (system and value):
            abort(400, 'for identifier search, must provide both '
                  '`system` and `value` params')
        ident = Identifier.query.filter_by(system=system, _value=value).first()
        if not ident:
            abort(404, 'no identifiers found for system `{}`, '
                  'value `{}`'.format(system, value))
        query = query.join(
            PractitionerIdentifier).filter(and_(
                PractitionerIdentifier.identifier_id == ident.id,
                PractitionerIdentifier.practitioner_id == Practitioner.id))

    practs = [p.as_fhir() for p in query]

    bundle = {
        'resourceType': 'Bundle',
        'updated': FHIR_datetime.now(),
        'total': len(practs),
        'type': 'searchset',
        'link': {
            'rel': 'self',
            'href': url_for(
                'practitioner_api.practitioner_search', _external=True),
        },
        'entry': practs
    }

    return jsonify(bundle)


@practitioner_api.route('/practitioner/<string:id_or_code>')
@oauth.require_oauth()
def practitioner_get(id_or_code):
    """Access to the requested practitioner as a FHIR resource

    If 'system' param is provided, looks up the user by identifier,
    using the `id_or_code` string as the identifier value; otherwise,
    treats `id_or_code` as the practitioner.id

    ---
    operationId: practitioner_get
    tags:
      - Practitioner
    produces:
      - application/json
    parameters:
      - name: id_or_code
        in: path
        description: TrueNTH practitioner ID OR Identifier value code
        required: true
        type: string
    responses:
      200:
        description:
          Returns the requested practitioner as a FHIR [practitioner
          resource](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    system = request.args.get('system')
    if system:
        ident = Identifier.query.filter_by(
            system=system, _value=id_or_code).first()
        if not ident:
            abort(404, 'no identifiers found for system `{}`, '
                  'value `{}`'.format(system, id_or_code))
        practitioner = Practitioner.query.join(
            PractitionerIdentifier).filter(and_(
                PractitionerIdentifier.identifier_id == ident.id,
                PractitionerIdentifier.practitioner_id == Practitioner.id)
            ).first()
        if not practitioner:
            abort(404, 'no practitioner found with identifier: system `{}`, '
                  'value `{}`'.format(system, id_or_code))
    else:
        check_int(id_or_code)
        practitioner = Practitioner.query.get_or_404(id_or_code)
    return jsonify(practitioner.as_fhir())


@practitioner_api.route('/practitioner', methods=('POST',))
@oauth.require_oauth()
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
def practitioner_post():
    """Add a new practitioner.  Updates should use PUT

    Returns the JSON FHIR practitioner as known to the system after adding.

    Submit JSON format [Practitioner
    Resource](https://www.hl7.org/fhir/DSTU2/practitioner.html) to add an
    practitioner.

    ---
    operationId: practitioner_post
    tags:
      - Practitioner
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          id: FHIRPractitioner
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Practitioner
    responses:
      200:
        description:
          Returns created [FHIR practitioner
          resource](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      400:
        description:
          if practitioner FHIR JSON is not valid
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    if (not request.json or 'resourceType' not in request.json or
            request.json['resourceType'] != 'Practitioner'):
        abort(400, "Requires FHIR resourceType of 'Practitioner'")
    try:
        practitioner = Practitioner.from_fhir(request.json)
    except MissingReference, e:
        abort(400, str(e))
    db.session.add(practitioner)
    db.session.commit()
    auditable_event("created new practitioner {}".format(practitioner),
                    user_id=current_user().id, subject_id=current_user().id,
                    context='user')
    return jsonify(practitioner.as_fhir())


@practitioner_api.route('/practitioner/<int:practitioner_id>',
                        methods=('PUT',))
@oauth.require_oauth()  # for service token access, oauth must come first
@roles_required([ROLE.ADMIN, ROLE.SERVICE])
def practitioner_put(practitioner_id):
    """Update practitioner via FHIR Resource Practitioner. New should POST

    Submit JSON format [Practitioner
    Resource](https://www.hl7.org/fhir/DSTU2/practitioner.html) to update an
    existing practitioner.

    ---
    operationId: practitioner_put
    tags:
      - Practitioner
    produces:
      - application/json
    parameters:
      - name: practitioner_id
        in: path
        description: TrueNTH practitioner ID
        required: true
        type: integer
        format: int64
      - in: body
        name: body
        schema:
          id: FHIRPractitioner
          required:
            - resourceType
          properties:
            resourceType:
              type: string
              description: defines FHIR resource type, must be Practitioner
    responses:
      200:
        description:
          Returns updated [FHIR Practitioner
          resource](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      400:
        description:
          if practitioner FHIR JSON is not valid
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
          to view requested patient

    """
    check_int(practitioner_id)
    if (not request.json or 'resourceType' not in request.json or
            request.json['resourceType'] != 'Practitioner'):
        abort(400, "Requires FHIR resourceType of 'Practitioner'")
    practitioner = Practitioner.query.get_or_404(practitioner_id)
    try:
        practitioner.update_from_fhir(request.json)
    except MissingReference, e:
        abort(400, str(e))
    db.session.commit()
    auditable_event("updated practitioner from input {}".format(
        json.dumps(request.json)), user_id=current_user().id,
        subject_id=current_user().id, context='user')
    return jsonify(practitioner.as_fhir())
