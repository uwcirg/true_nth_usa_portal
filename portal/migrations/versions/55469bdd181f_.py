"""Correct QNR qb_id when assigned to the incorrect research protocol

Revision ID: 55469bdd181f
Revises: 9026af5fe040
Create Date: 2019-02-04 13:36:04.709868

"""
from portal.database import db
from portal.models.qb_status import QB_Status
from portal.models.qb_timeline import QBT, invalidate_users_QBT
from portal.models.questionnaire_bank import QuestionnaireBank
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.research_protocol import ResearchProtocol
from portal.models.user import User, active_patients
from portal.models.overall_status import OverallStatus

# revision identifiers, used by Alembic.
revision = '55469bdd181f'
down_revision = '9026af5fe040'


def qb_pairs_by_rp():
    """Lookup and generate a map of RP2->RP3 versions of QBs

    Issue only applies to IRONMAN RPs - ignore others
    """
    rp2_id = ResearchProtocol.query.filter_by(name='IRONMAN v2').one().id
    rp3_id = ResearchProtocol.query.filter_by(name='IRONMAN v3').one().id

    qb_map = dict()  # keyed by the RP2 QB ID
    for qb in QuestionnaireBank.query.filter_by(research_protocol_id=rp2_id):
        rp3_name = "IRONMAN_v3" + qb.name[len('IRONMAN'):]
        rp3_qb = QuestionnaireBank.query.filter_by(name=rp3_name).one()
        assert (rp3_qb.research_protocol_id == rp3_id)
        qb_map[qb.id] = rp3_qb.id
    return qb_map


def upgrade():
    # Tricky task to locate the errors.  One time expensive process,
    # loop through patients identifying problems.

    qb_map = qb_pairs_by_rp()
    fix_map = dict()

    for patient in active_patients(include_test_role=True).order_by(User.id):
        qnrs = QuestionnaireResponse.query.filter(
            QuestionnaireResponse.subject_id == patient.id).order_by(
            QuestionnaireResponse.authored)
        if not qnrs.count():
            # Only care if the user submitted QNRs:
            continue

        for qnr in qnrs:

            # Obtain qb_timeline row at the time of QNR.authored
            as_of_date = qnr.authored
            qbt = QBT.query.filter(QBT.user_id == patient.id).filter(
                QBT.at <= as_of_date).order_by(
                QBT.at.desc(), QBT.id.desc()).first()

            if qnr.questionnaire_bank_id is None:
                print ("user_id {} authored {} {} with NO qb_id set".format(
                    patient.id,
                    as_of_date,
                    qnr.document['questionnaire']['reference']))
                continue
            if qbt and qbt.status != OverallStatus.withdrawn:
                recorded_qb = QuestionnaireBank.query.get(
                    qnr.questionnaire_bank_id)
                qbd = qbt.qbd()
                expected_qb = qbd.questionnaire_bank
                if recorded_qb.classification == 'indefinite':
                    # indefinite case is handled differently...
                    qb_status = QB_Status(patient, as_of_date)
                    expected_qb = QuestionnaireBank.query.get(
                        qb_status._current_indef.qb_id)

                if recorded_qb != expected_qb:
                    replacement = qb_map.get(recorded_qb.id)
                    if replacement == expected_qb.id:
                        # retain the change request, as altering it inline
                        # interrupts the iteration
                        fix_map[qnr.id] = expected_qb.id
                        print(
                            "qnr {} replacing incorrect qb_id {} with {} "
                            "for user {}".format(
                                qnr.id, recorded_qb.id, expected_qb.id,
                                patient.id))

                    else:
                        print(
                            "PROBLEM: recorded qb_id {}, "
                            "expected {} doesn't match replacement {} "
                            "for user_id {}".format(
                                recorded_qb.id, expected_qb.id,
                                replacement, patient.id))

        for qnr_id, qb_id in fix_map.items():
            qnr = QuestionnaireResponse.query.get(qnr_id)
            qnr.questionnaire_bank_id = qb_id

            # clear out cached qb_timeline data for user as it
            # needs to be recalculated given the change
            invalidate_users_QBT(qnr.subject_id)

        db.session.commit()

def downgrade():
    # not restoring that mess.  idempotent to run again
    pass
