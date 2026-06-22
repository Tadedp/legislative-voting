// Enums mapping directly to PostgreSQL Domain Types
export type SessionStatus = 'PENDING' | 'ACTIVE' | 'PAUSED' | 'CLOSED';
export type ItemStatus = 'DRAFT' | 'DEBATE' | 'APPROVED_IN_GENERAL' | 'SANCTIONED' | 'REJECTED' | 'POSTPONED';
export type RoundStatus = 'DRAFT' | 'VOTING_OPEN' | 'VOTING_CLOSED' | 'RESOLVED' | 'TIED' | 'ABORTED' | 'VOIDED';

// Core Entities
export interface ActiveAgendaItem {
  id: string;
  title: string;
  summary: string;
  status: ItemStatus;
  file_number?: string;
  category?: string;
}

export interface ActiveVotingRound {
  id: string;
  agenda_item_id: string;
  stage: string;
  specific_reference?: string;
  is_nominal: boolean;
  presiding_officer_id: string | null;
  president_votes_ordinarily: boolean;
  time_limit_seconds?: number;
  status: RoundStatus;
  certified_quorum_count?: number;
}

export interface LegislativeSession {
  id: string;
  title: string;
  status: SessionStatus;
  presiding_officer_id: string | null;
}

// REST Rehydration Payload (GET legislative-sessions/current)
export interface CurrentStateResponse {
  session: LegislativeSession | null;
  active_agenda_item: ActiveAgendaItem | null;
  active_voting_round: ActiveVotingRound | null;
}

// WebSocket Event Structure
export interface OrchestratorEvent {
  event_type: 'SESSION_STATUS_CHANGED' | 'AGENDA_ITEM_UPDATED' | 'VOTING_ROUND_OPENED' | 'VOTING_ROUND_CLOSED' | 'VOTING_ROUND_ABORTED' | 'VOTING_ROUND_RESOLVED' | 'VOTING_ROUND_TIED' | 'VOTE_CAST' | 'QUORUM_WARNING';
  data: any; // Mapped to the specific event delta
  timestamp: string;
}
