"""empty message

Revision ID: 156d9b04d4bc
Revises: 923b0f523f3
Create Date: 2015-06-22 17:09:20.180760

"""

# revision identifiers, used by Alembic.
revision = '156d9b04d4bc'
down_revision = '923b0f523f3'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM


gender_types = ENUM('male', 'female', 'undifferentiated', name='genders',
        create_type=False)

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    gender_types.create(op.get_bind(), checkfirst=False)
    op.add_column('users', sa.Column('gender', gender_types, nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=40), nullable=True))
    op.create_unique_constraint(None, 'users', ['phone'])
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'phone')
    op.drop_column('users', 'gender')
    gender_types.drop(op.get_bind(), checkfirst=False)
    ### end Alembic commands ###
