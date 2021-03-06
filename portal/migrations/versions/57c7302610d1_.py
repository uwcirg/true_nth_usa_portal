"""empty message

Revision ID: 57c7302610d1
Revises: e7682ee1276f
Create Date: 2017-02-28 15:05:28.445646

"""

# revision identifiers, used by Alembic.
revision = '57c7302610d1'
down_revision = 'e7682ee1276f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

status_types = ENUM('planned', 'arrived', 'in-progress', 'onleave', 'finished',
                    'cancelled', name='statuses', create_type=False)

auth_method_types = ENUM('password_authenticated', 'url_authenticated',
                         'staff_authenticated', 'staff_handed_to_patient',
                         name='auth_methods', create_type=False)


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    status_types.create(op.get_bind(), checkfirst=False)
    auth_method_types.create(op.get_bind(), checkfirst=False)
    op.create_table('encounters',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('status', status_types, nullable=False),
                    sa.Column('auth_method', auth_method_types,
                              nullable=False),
                    sa.Column('start_time', sa.DateTime(), nullable=False),
                    sa.Column('end_time', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('encounters')
    status_types.drop(op.get_bind(), checkfirst=False)
    auth_method_types.drop(op.get_bind(), checkfirst=False)
    ### end Alembic commands ###
