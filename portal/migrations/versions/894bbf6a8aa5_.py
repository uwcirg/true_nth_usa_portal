 """encode irondemog QuestionnaireResponse answers

Revision ID: 894bbf6a8aa5
Revises: d4517f61aaed
Create Date: 2020-03-12 20:43:49.177994

"""
import copy

from alembic import op
from sqlalchemy.orm import sessionmaker

from portal.models.questionnaire_response import QuestionnaireResponse
from portal.models.questionnaire import Questionnaire

# revision identifiers, used by Alembic.
revision = '894bbf6a8aa5'
down_revision = 'd4517f61aaed'

Session = sessionmaker()


# questions that allow multiple answers
checkbox_questions = {
    # comorbidities
    'comorb.1',

    # tobacco
    'irondemog.13',
    'irondemog_v3.13',

    # living arrangement
    'irondemog.15',
    'irondemog_v3.15',

    # supplements
    'irondemog.25',
    'irondemog_v3.25',

    # ethnic group
    'irondemog.26',
    'irondemog_v3.26',

    # colorectal cancer
    'irondemog.28',
    'irondemog_v3.29',

    # prostate cancer
    'irondemog.32',
    'irondemog_v3.36',

    # breast cancer
    'irondemog.39',
    'irondemog_v3.43',

    # ovarian cancer
    'irondemog.42',
    'irondemog_v3.48',

    # pancreatic cancer
    'irondemog_v3.53',

    # melanoma
    'irondemog_v3.60',
}


def fixup_qnr(questionnaire_response_json, questionnaire_option_map):
    """Replace valueString text with corresponding valueCoding"""

    # JSONB mutation detection work around
    # See https://bugs.launchpad.net/fuel/+bug/1482658
    qnr_json_copy = copy.deepcopy(questionnaire_response_json)

    for question in qnr_json_copy['group']['question']:
        # skip unaffected questions
        if question['linkId'] not in checkbox_questions:
            continue

        fixed_answers = []
        for answer in question['answer']:
            if 'valueCoding' in answer:
                seen_codes = {a['valueCoding']['code'] for a in fixed_answers if 'valueCoding' in a}

                # check for duplicate codes
                if answer['valueCoding']['code'] not in seen_codes:
                    fixed_answers.append(answer)
                    continue

            # encode strings as codes
            if 'valueString' in answer:
                coded_answer = {'valueCoding': {
                    # lookup code from valueString
                    'code': questionnaire_option_map[answer['valueString']],
                    'system': 'https://eproms.truenth.org/api/codings/assessment',
                }}
                fixed_answers.append(coded_answer)
                continue

            # catch any other answer types
            fixed_answers.append(answer)

        question['answer'] = fixed_answers
    return qnr_json_copy


def upgrade():
    session = Session(bind=op.get_bind())

    instrument_ids = ('comorb', 'irondemog', 'irondemog_v3')

    for instrument_id in instrument_ids:
        questionnaire = Questionnaire.find_by_name(name=instrument_id)
        # exit if Questionnaire not found
        if not questionnaire:
            return

        # invert dictionary to lookup code by answer
        q_codes = {v: k for k, v in questionnaire.questionnaire_code_map().items()}

        questionnaire_responses = session.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.document[
                ("questionnaire", "reference")
            ].astext.endswith(instrument_id)
        ).order_by(QuestionnaireResponse.id)
        for qnr in questionnaire_responses:
            qnr_json = fixup_qnr(qnr.document, questionnaire_option_map=q_codes)
            if qnr_json == qnr.document:
                continue

            qnr.document = qnr_json
            session.add(qnr)
            session.commit()
            assert qnr.document
            print("Processed QNR: %d" % qnr.id)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###