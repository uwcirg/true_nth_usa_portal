from alembic import op
import sqlalchemy as sa

"""empty message

Revision ID: 91351a73e6e2
Revises: 63262fe95b9c
Create Date: 2018-03-08 15:34:22.391417

"""

# revision identifiers, used by Alembic.
revision = '91351a73e6e2'
down_revision = '63262fe95b9c'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('interventions', sa.Column('subscribed_events', sa.Integer()))
    op.execute('UPDATE interventions SET subscribed_events=0')
    op.alter_column('interventions', 'subscribed_events', nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('interventions', 'subscribed_events')
    # ### end Alembic commands ###
