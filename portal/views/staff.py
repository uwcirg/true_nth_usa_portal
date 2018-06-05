from flask import Blueprint, jsonify, render_template
from flask_user import roles_required
from sqlalchemy import and_

from ..extensions import oauth
from ..models.app_text import (
    InitialConsent_ATMA,
    MailResource,
    StaffRegistrationEmail_ATMA,
    UndefinedAppText,
    VersionedResource,
    app_text
)
from ..models.communication import load_template_args
from ..models.organization import Organization, OrgTree, UserOrganization
from ..models.role import ROLE, Role
from ..models.user import User, UserRoles, current_user, get_user_or_abort

staff = Blueprint('staff', __name__)


@staff.route('/staff-registration-email/<int:user_id>')
@roles_required([ROLE.ADMIN, ROLE.STAFF_ADMIN])
@oauth.require_oauth()
def staff_registration_email(user_id):
    """Staff Registration Email Content"""
    if user_id:
        user = get_user_or_abort(user_id)
    else:
        user = current_user()

    org = user.first_top_organization()
    args = load_template_args(user=user)

    try:
        name_key = StaffRegistrationEmail_ATMA.name_key(organization=org)
        item = MailResource(
            app_text(name_key), locale_code=user.locale_code, variables=args)
    except UndefinedAppText:
        """return no content and 204 no content status"""
        return '', 204

    return jsonify(subject=item.subject, body=item.body)


@staff.route('/staff-profile-create')
@roles_required(ROLE.STAFF_ADMIN)
@oauth.require_oauth()
def staff_profile_create():
    user = current_user()
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)

    # compiling org list for staff
    # org list should include all orgs under the current user's org(s)
    ot = OrgTree()
    org_list = set()
    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(ot.here_and_below_id(org.id))

    return render_template(
        "profile/staff_profile_create.html", user=user,
        consent_agreements=consent_agreements,
        org_list=list(org_list))


@staff.route('/staff_profile/<int:user_id>')
@roles_required(ROLE.STAFF_ADMIN)
@oauth.require_oauth()
def staff_profile(user_id):
    """staff profile view function"""
    user = get_user_or_abort(user_id)
    consent_agreements = Organization.consent_agreements(
        locale_code=user.locale_code)
    terms = VersionedResource(
        app_text(InitialConsent_ATMA.name_key()),
        locale_code=user.locale_code)

    # compiling org list for staff admin user
    # org list should include all orgs under the current user's org(s)
    ot = OrgTree()
    org_list = set()
    for org in current_user().organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(ot.here_and_below_id(org.id))

    return render_template(
        'profile/staff_profile.html', user=user, terms=terms,
        current_user=current_user(), org_list=list(org_list),
        consent_agreements=consent_agreements)


@staff.route('/staff')
@roles_required(ROLE.STAFF_ADMIN)
@oauth.require_oauth()
def staff_index():
    """staff view function, intended for staff admin

    Present the logged in staff admin the list of staff matching
    the staff admin's organizations (and any decendent organizations)

    """
    user = current_user()

    ot = OrgTree()
    staff_role_id = Role.query.filter(
        Role.name == ROLE.STAFF).with_entities(Role.id).first()
    admin_role_id = Role.query.filter(
        Role.name == ROLE.ADMIN).with_entities(Role.id).first()
    staff_admin_role_id = Role.query.filter(
        Role.name == ROLE.STAFF_ADMIN).with_entities(Role.id).first()

    # empty patient query list to start, unionize with other relevant lists
    staff_list = User.query.filter(User.id == -1)

    org_list = set()

    user_orgs = set()

    # Build list of all organization ids, and their decendents, the
    # user belongs to
    for org in user.organizations:
        if org.id == 0:  # None of the above doesn't count
            continue
        org_list.update(ot.here_and_below_id(org.id))
        user_orgs.add(org.id)

    # Gather up all staff admin and admin that belongs to user's org(s)
    admin_staff = User.query.join(UserRoles).filter(
        and_(User.id == UserRoles.user_id,
             UserRoles.role_id.in_([admin_role_id, staff_admin_role_id])
             )
        ).join(UserOrganization).filter(
            and_(UserOrganization.user_id == User.id,
                 UserOrganization.organization_id.in_(user_orgs)))
    admin_list = [u.id for u in admin_staff]

    # Gather up all staff belonging to any of the orgs (and their children)
    # NOTE, need to exclude staff_admin or admin user at the same org(s) as the user
    # as the user should NOT be able to edit their record
    org_staff = User.query.join(UserRoles).filter(
        and_(User.id == UserRoles.user_id,
             ~User.id.in_(admin_list),
             UserRoles.role_id == staff_role_id
             )
        ).join(UserOrganization).filter(
            and_(UserOrganization.user_id == User.id,
                 UserOrganization.organization_id.in_(org_list)))
    staff_list = staff_list.union(org_staff).all()

    # only show test users to admins
    if not user.has_role(ROLE.ADMIN):
        staff_list = [s for s in staff_list if not s.has_role(ROLE.TEST)]

    return render_template(
        'admin/staff_by_org.html', staff_list=staff_list,
        user=user, wide_container="true")
