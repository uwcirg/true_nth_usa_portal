"""empty message

Revision ID: 23b47479c442
Revises: 5d1daa0f3a14
Create Date: 2017-05-10 12:31:14.341117

"""

# revision identifiers, used by Alembic.
revision = '23b47479c442'
down_revision = 'b92dc277c384'

from alembic import op
import sqlalchemy as sa


def upgrade():
    classification_types_enum = sa.Enum(
        'baseline', 'recurring', 'indefinite', name='classification_enum')
    classification_types_enum.create(op.get_bind(), checkfirst=False)
    op.add_column(
        'questionnaire_banks',
        sa.Column(
            'classification', classification_types_enum,
            server_default='baseline', nullable=False))

    # add default to existing, then apply constraint
    #conn = op.get_bind()
    #conn.execute(text("""UPDATE questionnaire_banks SET
    #                  classification=:default"""), default='baseline')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('questionnaire_banks', 'classification')
    sa.Enum(name='classification_enum').drop(op.get_bind(), checkfirst=False)
    # ### end Alembic commands ###
