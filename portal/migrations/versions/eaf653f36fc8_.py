from alembic import op
import sqlalchemy as sa


"""empty message

Revision ID: eaf653f36fc8
Revises: f32ba62f1e77
Create Date: 2017-09-18 18:27:49.542019

"""

# revision identifiers, used by Alembic.
revision = 'eaf653f36fc8'
down_revision = 'f32ba62f1e77'


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'communication_requests',
        sa.Column(
            'lr_uuid',
            sa.Text(),
            nullable=False))
    op.add_column(
        'communication_requests',
        sa.Column(
            'notify_post_qb_start',
            sa.Text(),
            nullable=False))
    op.add_column(
        'communication_requests',
        sa.Column(
            'qb_iteration',
            sa.Integer(),
            nullable=True))
    op.drop_constraint(
        u'_communication_request_qb_days',
        'communication_requests',
        type_='unique')
    op.create_unique_constraint(
        '_communication_request_qb_days', 'communication_requests', [
            'questionnaire_bank_id', 'notify_post_qb_start', 'qb_iteration'])
    op.drop_column('communication_requests', 'notify_days_after_event')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'communication_requests',
        sa.Column(
            'notify_days_after_event',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False))
    op.drop_constraint(
        '_communication_request_qb_days',
        'communication_requests',
        type_='unique')
    op.create_unique_constraint(
        u'_communication_request_qb_days', 'communication_requests', [
            'questionnaire_bank_id', 'notify_days_after_event'])
    op.drop_column('communication_requests', 'qb_iteration')
    op.drop_column('communication_requests', 'notify_post_qb_start')
    op.drop_column('communication_requests', 'lr_uuid')
    # ### end Alembic commands ###
