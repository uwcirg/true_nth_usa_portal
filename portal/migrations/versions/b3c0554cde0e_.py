"""delete excess demographic questionnaire responses

Revision ID: b3c0554cde0e
Revises: 1977c23a53c8
Create Date: 2020-09-02 22:07:40.249193

"""
from alembic import op
from sqlalchemy import or_
from sqlalchemy.orm import sessionmaker

from portal.models.audit import Audit
from portal.models.qb_timeline import QBT
from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.user import User

Session = sessionmaker()

# revision identifiers, used by Alembic.
revision = 'b3c0554cde0e'
down_revision = '1977c23a53c8'


def faux_account(session):
    """Generates a fake user account to hold references to unwanted QNRs"""
    email = '__no_email__fake@example.com'
    user = session.query(User).filter(User._email == email).first()
    if not user:
        session.add(User(email=email))
        session.commit()
        user = session.query(User).filter(User.email == email).one()
    return user


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    bind = op.get_bind()
    session = Session(bind=bind)

    # Rather than blow away the unwanted QNRs, assign them to a fake subject
    fu = faux_account(session)

    query = session.query(QuestionnaireResponse).filter(
        QuestionnaireResponse.subject_id != fu.id).filter(or_(
            QuestionnaireResponse.document[
                "questionnaire"]["reference"].astext.endswith("irondemog"),
            QuestionnaireResponse.document[
                "questionnaire"]["reference"].astext.endswith("irondemog_v3")
        )).order_by(
            QuestionnaireResponse.subject_id, QuestionnaireResponse.authored)

    if not query.count():
        return

    def reassign_unwanted(qnrs):
        first_completed = None
        need_relationship_assignments = set()
        for qnr in qnrs:
            if not first_completed and qnr.status == 'completed':
                first_completed = qnr
                if not qnr.questionnaire_bank_id:
                    need_relationship_assignments.add(qnr.subject_id)
            elif first_completed:
                msg = (
                    f"reassigning QuestionnaireResponse: {qnr.id} "
                    f"from subject {qnr.subject_id} to fake {fu.id}")
                aud = Audit(
                    user_id=fu.id,
                    subject_id=qnr.subject_id,
                    context='assessment',
                    comment=msg)
                print(msg)
                session.add(aud)
                qnr.subject_id = fu.id

        return need_relationship_assignments

    cur_subject_id = 0
    batch = []
    subj_needing_updates = set()
    for qnr in query:
        if cur_subject_id and qnr.subject_id != cur_subject_id:
            subj_needing_updates.update(reassign_unwanted(batch))
            batch.clear()
        cur_subject_id = qnr.subject_id
        batch.append(qnr)
    subj_needing_updates.update(reassign_unwanted(batch))
    session.commit()

    # Flush timeline data / QNR->QB associations
    for subj_id in subj_needing_updates:
        print(f"purge timeline, QNR->QB associations for {subj_id}")
        qnrs = session.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.subject_id == subj_id).filter(
            QuestionnaireResponse.questionnaire_bank_id.isnot(None))
        for qnr in qnrs:
            qnr.questionnaire_bank_id = None
            qnr.qb_iteration = None
        session.query(QBT).filter(QBT.user_id == subj_id).delete()


def downgrade():
    # could pull out audit details and reassign, but don't see value atm
    pass
