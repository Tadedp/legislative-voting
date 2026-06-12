from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '841cd2bde874'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agenda_items',
    sa.Column('category', sa.Enum('PROJECT', 'MOTION', name='item_category'), nullable=False),
    sa.Column('file_number', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('parliamentary_stage', sa.Enum('INITIAL', 'REVISION', name='parliamentary_stage'), server_default=sa.text("'INITIAL'"), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'DEBATE', 'APPROVED_IN_GENERAL', 'APPROVED', 'SANCTIONED', 'REJECTED', 'POSTPONED', name='item_status'), server_default=sa.text("'DRAFT'"), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agenda_items'))
    )
    op.create_table('legislators',
    sa.Column('national_id', sa.Text(), nullable=False),
    sa.Column('full_name', sa.Text(), nullable=False),
    sa.Column('provisioning_token', sa.Text(), nullable=True),
    sa.Column('provisioning_token_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provisioning_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_legislators')),
    sa.UniqueConstraint('national_id', name=op.f('uq_legislators_national_id'))
    )
    op.create_index(op.f('ix_legislators_provisioning_token'), 'legislators', ['provisioning_token'], unique=True)
    op.create_table('system_users',
    sa.Column('username', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'PRESIDENCY', 'AUDITOR', 'SECRETARY', name='system_user_role'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_system_users'))
    )
    op.create_index('uq_system_users_username_lower', 'system_users', [sa.literal_column('lower(username)')], unique=True)
    op.create_table('voting_types',
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('allows_abstentions', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('approval_threshold', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('calc_base', sa.Enum('VOTES_CAST', 'MEMBERS_PRESENT', 'TOTAL_MEMBERS', name='calculation_base'), server_default=sa.text("'VOTES_CAST'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_voting_types')),
    sa.UniqueConstraint('name', name=op.f('uq_voting_types_name'))
    )
    op.create_table('devices',
    sa.Column('legislator_id', sa.UUID(), nullable=False),
    sa.Column('hardware_fingerprint', sa.Text(), nullable=False),
    sa.Column('public_key_pem', sa.Text(), nullable=False),
    sa.Column('device_token', sa.Text(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['legislator_id'], ['legislators.id'], name=op.f('fk_devices_legislator_id_legislators')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_devices')),
    sa.UniqueConstraint('device_token', name=op.f('uq_devices_device_token')),
    sa.UniqueConstraint('hardware_fingerprint', name=op.f('uq_devices_hardware_fingerprint')),
    sa.UniqueConstraint('legislator_id', name=op.f('uq_devices_legislator_id'))
    )
    op.create_table('legislative_sessions',
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'ACTIVE', 'PAUSED', 'CLOSED', name='legislative_session_status'), server_default=sa.text("'PENDING'"), nullable=False),
    sa.Column('ephemeral_public_key', sa.Text(), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('pres_type', sa.Enum('EX_OFFICIO', 'LEGISLATOR', name='president_type'), server_default=sa.text("'EX_OFFICIO'"), nullable=False),
    sa.Column('presiding_officer_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['presiding_officer_id'], ['legislators.id'], name=op.f('fk_legislative_sessions_presiding_officer_id_legislators'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_legislative_sessions'))
    )
    op.create_table('system_users_sessions',
    sa.Column('session_id', sa.Text(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('ip_address', sa.Text(), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['system_users.id'], name=op.f('fk_system_users_sessions_user_id_system_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('session_id', name=op.f('pk_system_users_sessions'))
    )
    op.create_table('session_attendances',
    sa.Column('id', sa.Uuid(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('legislative_session_id', sa.UUID(), nullable=False),
    sa.Column('legislator_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('PRESENT', 'ABSENT', 'ON_LEAVE', name='attendance_status'), server_default=sa.text("'PRESENT'"), nullable=False),
    sa.Column('registered_by', sa.UUID(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['legislative_session_id'], ['legislative_sessions.id'], name=op.f('fk_session_attendances_legislative_session_id_legislative_sessions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['legislator_id'], ['legislators.id'], name=op.f('fk_session_attendances_legislator_id_legislators'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['registered_by'], ['system_users.id'], name=op.f('fk_session_attendances_registered_by_system_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_session_attendances')),
    sa.UniqueConstraint('legislative_session_id', 'legislator_id', name='uq_session_attendances_session_legislator')
    )
    op.create_table('voting_rounds',
    sa.Column('agenda_item_id', sa.UUID(), nullable=False),
    sa.Column('legislative_session_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.Enum('SINGLE', 'GENERAL', 'SPECIFIC', name='round_stage'), nullable=False),
    sa.Column('specific_reference', sa.Text(), nullable=True),
    sa.Column('voting_type_id', sa.UUID(), nullable=False),
    sa.Column('is_nominal', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'VOTING_OPEN', 'VOTING_CLOSED', 'RESOLVED', 'TIED', 'ABORTED', 'VOIDED', name='round_status'), server_default=sa.text("'DRAFT'"), nullable=False),
    sa.Column('result', sa.Text(), nullable=True),
    sa.Column('quorum_present_count', sa.Integer(), nullable=True),
    sa.Column('certified_quorum_count', sa.Integer(), nullable=True),
    sa.Column('time_limit_seconds', sa.Integer(), nullable=True),
    sa.Column('president_votes_ordinarily', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('tie_breaker_vote_value', sa.Text(), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['agenda_item_id'], ['agenda_items.id'], name=op.f('fk_voting_rounds_agenda_item_id_agenda_items')),
    sa.ForeignKeyConstraint(['legislative_session_id'], ['legislative_sessions.id'], name=op.f('fk_voting_rounds_legislative_session_id_legislative_sessions')),
    sa.ForeignKeyConstraint(['voting_type_id'], ['voting_types.id'], name=op.f('fk_voting_rounds_voting_type_id_voting_types')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_voting_rounds'))
    )
    op.create_index('idx_voting_rounds_session_id', 'voting_rounds', ['legislative_session_id'], unique=False)
    op.create_table('nominal_votes',
    sa.Column('event_id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('voting_round_id', sa.UUID(), nullable=False),
    sa.Column('legislator_id', sa.UUID(), nullable=False),
    sa.Column('vote_value', sa.Enum('AFFIRMATIVE', 'NEGATIVE', 'ABSTENTION', name='vote_value'), nullable=False),
    sa.Column('cryptographic_signature', sa.Text(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['legislator_id'], ['legislators.id'], name=op.f('fk_nominal_votes_legislator_id_legislators')),
    sa.ForeignKeyConstraint(['voting_round_id'], ['voting_rounds.id'], name=op.f('fk_nominal_votes_voting_round_id_voting_rounds')),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_nominal_votes')),
    sa.UniqueConstraint('voting_round_id', 'legislator_id', name='uq_nominal_votes_voting_round_legislator')
    )
    op.create_table('non_nominal_tallies',
    sa.Column('id', sa.Uuid(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('voting_round_id', sa.UUID(), nullable=False),
    sa.Column('vote_value', sa.Enum('AFFIRMATIVE', 'NEGATIVE', 'ABSTENTION', name='vote_value'), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['voting_round_id'], ['voting_rounds.id'], name=op.f('fk_non_nominal_tallies_voting_round_id_voting_rounds'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_non_nominal_tallies'))
    )
    op.create_table('non_nominal_voters',
    sa.Column('id', sa.Uuid(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('voting_round_id', sa.UUID(), nullable=False),
    sa.Column('legislator_id', sa.UUID(), nullable=False),
    sa.Column('cryptographic_signature', sa.Text(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['legislator_id'], ['legislators.id'], name=op.f('fk_non_nominal_voters_legislator_id_legislators'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['voting_round_id'], ['voting_rounds.id'], name=op.f('fk_non_nominal_voters_voting_round_id_voting_rounds'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_non_nominal_voters')),
    sa.UniqueConstraint('voting_round_id', 'legislator_id', name='uq_non_nominal_voters_voting_round_legislator')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('non_nominal_voters')
    op.drop_table('non_nominal_tallies')
    op.drop_table('nominal_votes')
    op.drop_index('idx_voting_rounds_session_id', table_name='voting_rounds')
    op.drop_table('voting_rounds')
    op.drop_table('session_attendances')
    op.drop_table('system_users_sessions')
    op.drop_table('legislative_sessions')
    op.drop_table('devices')
    op.drop_table('voting_types')
    op.drop_index('uq_system_users_username_lower', table_name='system_users')
    op.drop_table('system_users')
    op.drop_index(op.f('ix_legislators_provisioning_token'), table_name='legislators')
    op.drop_table('legislators')
    op.drop_table('agenda_items')
    # ### end Alembic commands ###
