from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from portal.models.fhir import QuestionnaireResponse

"""Reindex irondemog_v3 questions

Revision ID: 8efa45d83a3b
Revises: b4dcf331317e
Create Date: 2018-07-23 12:58:12.567890

"""

# revision identifiers, used by Alembic.
revision = '8efa45d83a3b'
down_revision = 'b4dcf331317e'

Session = sessionmaker()


def increment_linkId(linkId):
    instrument_id, question_index = linkId.split('.')

    return "{instrument_id}.{question_index}".format(
        instrument_id=instrument_id,
        question_index=int(question_index)+1,
    )


def increment_code(code):
    instrument_id, question_index, option_index = code.split('.')

    return "{instrument_id}.{question_index}.{option_index}".format(
        instrument_id=instrument_id,
        question_index=int(question_index)+1,
        option_index=option_index,
    )


def reindex_questions(questionnaire_response_json):
    """Copy and modify QuestionnaireResponse codes"""
    qnr_json_copy = dict(questionnaire_response_json)

    for question in qnr_json_copy['group']['question']:
        question['linkId'] = increment_linkId(question['linkId'])

        for answer in question['answer']:
            coding_answer_data = answer.get('valueCoding')
            if not coding_answer_data:
                continue

            coding_answer_data['code'] = increment_code(coding_answer_data['code'])
    return qnr_json_copy


age_question_stub = {
    'text': 'What is your current age?',
    'answer': [],
    'linkId': 'irondemog.1',
}


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    session = Session(bind=op.get_bind())

    instrument_ids = ('irondemog', 'irondemog_v3')
    questionnaire_responses = session.query(QuestionnaireResponse).filter(sa.or_(
        QuestionnaireResponse.document[
            ("questionnaire", "reference")
        ].astext.endswith(instrument_id) for instrument_id in instrument_ids
    )).order_by(QuestionnaireResponse.id)

    for qnr in questionnaire_responses:
        qnr_json = reindex_questions(qnr.document)

        # add age question stub
        qnr_json['group']['question'].insert(0, age_question_stub)

        # "Reset" QNR to save updated data
        # Todo: fix JSONB mutation detection
        # See https://bugs.launchpad.net/fuel/+bug/1482658
        qnr.document = {}
        session.add(qnr)
        session.commit()

        qnr.document = qnr_json
        session.add(qnr)
        session.commit()
        assert qnr.document
        print("Processed QNR: %d" % qnr.id)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
