"""Patient view functions (i.e. not part of the API or auth)"""
from flask import abort, Blueprint, render_template
from flask_user import roles_required

from ..models.role import ROLE
from ..models.user import current_user, get_user
from ..extensions import oauth

patients = Blueprint('patients', __name__, url_prefix='/patients')

@patients.route('/')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def patients_root():
    """patients view function, intended for providers

    Present the logged in provider the list of patients matching
    the providers organizations

    """
    user = current_user()
    patients_by_org = {}
    for org in user.organizations:
        patients_by_org[org.name] = [user for user in org.users if
                                     user.has_role(ROLE.PATIENT)]

    return render_template(
        'patients_by_org.html', patients_by_org=patients_by_org, user=current_user(), wide_container="true")

@patients.route('/profile_create')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def profile_create():
    user = current_user()
    return render_template("profile_create.html", user = user)


@patients.route('/sessionReport/<int:user_id>')
def sessionReport(user_id):
    user = get_user(user_id)
    return render_template("sessionReport.html",user=user)


@patients.route('/patient_profile/<int:patient_id>')
@oauth.require_oauth()
@roles_required(ROLE.PROVIDER)
def patient_profile(patient_id):
    """individual patient view function, intended for providers"""
    user = current_user()
    user.check_role("edit", other_id=patient_id)
    patient = get_user(patient_id)
    if not patient:
        abort(404, "Patient {} Not Found".format(patient_id))

    return render_template('profile.html', user=patient,  providerPerspective="true")
