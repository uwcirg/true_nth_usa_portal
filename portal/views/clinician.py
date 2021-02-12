"""Clinician API view functions"""
from flask import Blueprint, jsonify, request, url_for
from flask_user import roles_required

from ..extensions import oauth
from ..models.fhir import bundle_results
from ..models.identifier import Identifier
from ..models.organization import org_restriction_by_role
from ..models.practitioner import Practitioner
from ..models.role import Role, ROLE
from ..models.user import User, UserOrganization, UserRoles, current_user
from ..system_uri import TRUENTH_ID
from .crossdomain import crossdomain

clinician_api = Blueprint('clinician_api', __name__)


def clinician_query(acting_user, org_filter=None):
    """Builds a live query for all clinicians the acting user can view"""
    query = User.query.join(UserRoles).filter(
        UserRoles.user_id == User.id).join(Role).filter(
        UserRoles.role_id == Role.id).filter(
        Role.name == ROLE.CLINICIAN.value).with_entities(
        User.id, User.first_name, User.last_name)

    limit_to_orgs = org_restriction_by_role(acting_user, org_filter)
    if limit_to_orgs:
        query = query.join(UserOrganization).filter(
            UserOrganization.user_id == User.id).filter(
            UserOrganization.organization_id.in_(limit_to_orgs))

    return query


@clinician_api.route('/api/clinician')
@crossdomain()
@roles_required([
    ROLE.CLINICIAN.value,
    ROLE.STAFF.value,
    ROLE.STAFF_ADMIN.value])
@oauth.require_oauth()
def clinician_search():
    """Obtain a bundle (list) of all clinicians current_user can view

    Returns a JSON FHIR bundle of clinicians and their organization.
    Results limited to clinicians with a common organization, or a child
    of the current user's organization(s).

    Can further limit results to those at or below a filter organization,
    such as a patient's org, by including query parameter
     ``/api/clinician?organization_id=###``

    ---
    operationId: clinician_search
    tags:
      - Clinician
    parameters:
      - name: org_filter
        in: query
        description:
            Limit the results beyond the current_user's view by including
            organization identifiers
            `/api/clinician?organization_id=146999`
        required: true
        type: string
    produces:
      - application/json
    responses:
      200:
        description:
          Returns a FHIR bundle of clinicians as [practitioner
          resources](http://www.hl7.org/fhir/DSTU2/practitioner.html) in JSON.
      401:
        description:
          if missing valid OAuth token or logged-in user lacks permission
    security:
      - ServiceToken: []

    """
    clinicians = []
    org_filter = request.args.getlist('organization_id', int)
    for item in clinician_query(current_user(), org_filter):
        clinicians.append(Practitioner(
            first_name=item.first_name,
            last_name=item.last_name,
            identifiers=[
                Identifier(use='official', system=TRUENTH_ID, value=item.id)
            ]).as_fhir())

    link = {
        'rel': 'self', 'href': url_for(
            'clinician_api.clinician_search', _external=True)}

    return jsonify(bundle_results(elements=clinicians, links=[link]))
