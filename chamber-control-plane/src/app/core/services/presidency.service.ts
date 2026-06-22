import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SessionStatus } from '../models/orchestrator.models';

export interface VotingType {
  id: string;
  name: string;
  allows_abstentions: boolean;
  approval_threshold: number;
  calc_base: string;
}

export interface VotingRoundCreate {
  agenda_item_id: string;
  stage: 'SINGLE' | 'GENERAL' | 'SPECIFIC';
  specific_reference?: string | null;
  voting_type_id: string;
  is_nominal: boolean;
  president_votes_ordinarily: boolean;
  time_limit_seconds?: number | null;
}

export interface VotingTally {
  affirmative: number;
  negative: number;
  abstentions: number;
  suggested_result: string;
}

export interface ProclamationPayload {
  affirmative: number;
  negative: number;
  abstentions: number;
}

export interface SessionCreate {
  title: string;
  pres_type: 'EX_OFFICIO' | 'LEGISLATOR';
  presiding_officer_id?: string;
}

@Injectable({
  providedIn: 'root'
})
export class PresidencyService {
  private readonly http = inject(HttpClient);

  // Session Control
  createSession(data: SessionCreate): Observable<any> {
    return this.http.post('/legislative-sessions', data);
  }

  updateSessionStatus(sessionId: string, status: SessionStatus): Observable<any> {
    return this.http.patch(`/legislative-sessions/${sessionId}/status`, { status });
  }

  // Voting Lifecycle
  createVotingRound(sessionId: string, data: VotingRoundCreate): Observable<any> {
    return this.http.post(`/legislative-sessions/${sessionId}/voting-rounds`, data);
  }

  openVotingRound(roundId: string): Observable<any> {
    return this.http.post(`/voting-rounds/${roundId}/open`, {});
  }

  closeVotingRound(roundId: string): Observable<any> {
    return this.http.post(`/voting-rounds/${roundId}/close`, {});
  }

  getRoundTally(roundId: string): Observable<VotingTally> {
    return this.http.get<VotingTally>(`/voting-rounds/${roundId}/tally`);
  }

  proclaimVotingRound(roundId: string, payload: ProclamationPayload): Observable<any> {
    return this.http.post(`/voting-rounds/${roundId}/proclaim`, payload);
  }

  rectifyVotingRound(roundId: string): Observable<any> {
    return this.http.post(`/voting-rounds/${roundId}/rectify`, {});
  }

  // Utilities
  getVotingTypes(): Observable<VotingType[]> {
    return this.http.get<VotingType[]>('/voting-types');
  }

  getAgendaItems(): Observable<any[]> {
    return this.http.get<any[]>('/agenda-items');
  }

  getLegislators(): Observable<any[]> {
    return this.http.get<any[]>('/legislators');
  }
}
