from alembic import op
import sqlalchemy as sa

"""empty message

Revision ID: 87014965d131
Revises: 4ec18346a368
Create Date: 2018-01-31 14:38:58.916094

"""

# revision identifiers, used by Alembic.
revision = '87014965d131'
down_revision = '4ec18346a368'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'practitioner_identifiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('practitioner_id', sa.Integer(), nullable=False),
        sa.Column('identifier_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['identifier_id'], ['identifiers.id'],
                                ondelete='cascade'),
        sa.ForeignKeyConstraint(['practitioner_id'], ['practitioners.id'],
                                ondelete='cascade'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('practitioner_id', 'identifier_id',
                            name='_practitioner_identifier')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('practitioner_identifiers')
    # ### end Alembic commands ###
