import { Injectable, inject, DestroyRef, signal, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { retry, timer, Subscription, repeat, timeout } from 'rxjs';
import { 
  LegislativeSession, 
  ActiveAgendaItem, 
  ActiveVotingRound, 
  OrchestratorEvent, 
  CurrentStateResponse 
} from '../models/orchestrator.models';
import { AuthService } from './auth.service';
import { Router } from '@angular/router';

@Injectable({
  providedIn: 'root'
})
export class StateSyncService {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  
  private socket$?: WebSocketSubject<OrchestratorEvent>;

  // Exclusive owner of application state
  readonly sessionState = signal<LegislativeSession | null>(null);
  readonly activeItem = signal<ActiveAgendaItem | null>(null);
  readonly votingRound = signal<ActiveVotingRound | null>(null);
  readonly isConnectionStable = signal<boolean>(false);
  readonly attendanceUpdated = signal<number>(0);
  
  // Aggregate Counters for Zero-Trust Display
  readonly tokensIssued = signal<number>(0);
  readonly votesReceived = signal<number>(0);

  private eventBuffer: OrchestratorEvent[] = [];
  private rehydrationSub: Subscription | null = null;
  private wsSubscription: Subscription | null = null;
  
  // Terminal states array for race condition guards
  private readonly terminalStates = ['RESOLVED', 'ABORTED', 'VOIDED'];

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      if (user) {
        if (!this.socket$ || this.socket$.closed) {
          this.wsSubscription?.unsubscribe();
          this.initializeWebSocket();
        }
      } else {
        this.disconnectWebSocket();
      }
    });
  }

  private disconnectWebSocket() {
    this.wsSubscription?.unsubscribe();
    this.wsSubscription = null;

    if (this.socket$) {
      this.socket$.complete();
      this.socket$ = undefined;
    }
    if (this.rehydrationSub) {
      this.rehydrationSub.unsubscribe();
      this.rehydrationSub = null;
    }
  }

  private initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/state`;

    this.socket$ = webSocket<OrchestratorEvent>({
      url: wsUrl,
      openObserver: {
        next: () => this.onConnectionEstablished()
      },
      closeObserver: {
        next: (closeEvent: CloseEvent) => {
          if (closeEvent && closeEvent.code === 1008) {
            console.warn('WebSocket Policy Violation (1008). Logging out.');
            this.auth.logout();
            this.router.navigate(['/auth/login']);
          } else {
            this.onConnectionLost();
          }
        }
      }
    });

    this.wsSubscription = this.socket$
      .pipe(
        retry({
          count: Infinity,
          delay: (error, retryCount) => {
            console.warn(`WebSocket connection failed. Retrying in ${Math.min(1000 * Math.pow(2, retryCount), 30000)}ms...`);
            return timer(Math.min(1000 * Math.pow(2, retryCount), 30000));
          }
        }),
        repeat({ delay: 1000 }),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe({
        next: (event) => this.handleEvent(event),
        error: (err) => console.error('WebSocket critical error:', err)
      });
  }

  private onConnectionEstablished() {
    console.log('WebSocket connection established. Triggering state rehydration...');
    this.rehydrateState();
  }

  private onConnectionLost() {
    console.warn('WebSocket connection lost. Engaging circuit breaker.');
    this.isConnectionStable.set(false);
    this.eventBuffer = []; 
    this.rehydrationSub?.unsubscribe();
  }

  rehydrateState() {
    if (this.rehydrationSub) {
      this.rehydrationSub.unsubscribe();
    }

    this.rehydrationSub = this.http.get<CurrentStateResponse>('/legislative-sessions/current')
      .pipe(
        timeout(5000),
        retry({
          count: Infinity,
          delay: (error, retryCount) => {
            if (error.status !== 0 && error.status !== undefined && error.status < 500) throw error;
            this.isConnectionStable.set(false);
            console.warn(`Rehydration failed. Retrying in ${Math.min(1000 * Math.pow(2, retryCount), 30000)}ms...`);
            return timer(Math.min(1000 * Math.pow(2, retryCount), 30000));
          }
        }),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe({
        next: (response) => {
          if (!this.socket$ || this.socket$.closed) {
            console.warn('Rehydration ignored: WebSocket disconnected during HTTP request.');
            return;
          }

          this.sessionState.set(response.session);
          this.activeItem.set(response.active_agenda_item);
          this.votingRound.set(response.active_voting_round);
          
          if (response.active_voting_round) {
            this.tokensIssued.set(response.active_voting_round.tokens_issued || 0);
            this.votesReceived.set(response.active_voting_round.votes_received || 0);
          } else {
            this.tokensIssued.set(0);
            this.votesReceived.set(0);
          }
          
          if (this.eventBuffer.length > 0) {
            this.eventBuffer.forEach(event => this.handleEvent(event, true));
            this.eventBuffer = [];
          }

          // Only after successful rehydration is the connection considered stable
          this.isConnectionStable.set(true);
          console.log('State successfully rehydrated and verified.');
        },
        error: (err) => {
          console.error('Failed to rehydrate state', err);
          if (err.status === 401 || err.status === 403) {
            this.isConnectionStable.set(true);
            this.router.navigate(['/auth/login']);
            return;
          }
          if (err.status === 404) {
            // A 404 means there is no active legislative session yet.
            this.sessionState.set(null);
            this.activeItem.set(null);
            this.votingRound.set(null);
            this.isConnectionStable.set(true);
            this.eventBuffer = [];
            return;
          }
          
          // Fallback handler for unhandled 4xx errors (e.g. 422, 400)
          console.warn('Unhandled HTTP error during rehydration. Unlocking UI and dropping stale events.');
          this.isConnectionStable.set(true);
          this.eventBuffer = [];
        }
      });
  }

  private handleEvent(event: OrchestratorEvent, isReplaying: boolean = false) {
    if (!event || !event.event_type) return;

    if (!this.isConnectionStable() && !isReplaying) {
      if (this.eventBuffer.length >= 1000) {
        console.warn('Event buffer overflow. Evicting oldest event.');
        this.eventBuffer.shift();
      }
      this.eventBuffer.push(event);
      return;
    }

    const currentRound = this.votingRound();
    if (currentRound && this.terminalStates.includes(currentRound.status)) {
      if (event.data && event.data.id === currentRound.id) {
        return;
      }
    }

    switch (event.event_type) {
      case 'SESSION_STATUS_CHANGED':
        this.sessionState.set(event.data);
        break;
      case 'AGENDA_ITEM_UPDATED':
        this.activeItem.set(event.data);
        break;
      case 'VOTING_ROUND_OPENED':
        this.votingRound.update(current => {
          if (current) {
            if (current.id === event.data?.id) {
              if (current.status === 'VOTING_OPEN') {
                return current;
              }
              if (current.status === 'VOTING_CLOSED' || this.terminalStates.includes(current.status)) {
                return current;
              }
            }
          }
          return event.data;
        });
        this.tokensIssued.set(0);
        this.votesReceived.set(0);
        break;
      case 'VOTING_ROUND_CLOSED':
        this.votingRound.update(current => {
          if (!current || current.id !== event.data?.id) return current;
          if (current.status !== 'VOTING_OPEN') return current;
          return { ...current, status: 'VOTING_CLOSED' };
        });
        break;
      case 'VOTING_ROUND_TIED':
        this.votingRound.update(current => {
          if (!current || current.id !== event.data?.id) return current;
          if (current.status !== 'VOTING_CLOSED') return current;
          return { ...current, status: 'TIED' };
        });
        break;
      case 'VOTING_ROUND_RESOLVED':
      case 'TIE_BREAKER_VOTE_CAST':
        this.votingRound.update(current => {
          if (!current || current.id !== event.data?.id) return current;
          if (current.status !== 'VOTING_CLOSED' && current.status !== 'TIED' && current.status !== 'VOTING_OPEN') return current;
          return { ...current, status: 'RESOLVED' };
        });
        break;
      case 'VOTING_ROUND_ABORTED':
      case 'VOTING_ROUND_VOIDED':
        this.votingRound.update(current => {
          if (!current || current.id !== event.data?.id) return current;
          if (current.status !== 'VOTING_CLOSED' && current.status !== 'TIED' && current.status !== 'VOTING_OPEN') return current;
          return { ...current, status: event.event_type === 'VOTING_ROUND_ABORTED' ? 'ABORTED' : 'VOIDED' };
        });
        break;
      case 'NON_NOMINAL_VOTE_AUTHORIZED':
        if (event.data?.current_tokens !== undefined) {
          this.tokensIssued.update(current => Math.max(current, event.data.current_tokens));
        }
        break;
      case 'NOMINAL_VOTE_CAST':
      case 'NON_NOMINAL_VOTE_CAST':
        if (event.data?.current_votes !== undefined) {
          this.votesReceived.update(current => Math.max(current, event.data.current_votes));
        }
        break;
      case 'QUORUM_WARNING':
        console.warn(`Quorum warning received: ${event.data?.connected}/${event.data?.minimum_required}`);
        break;
      case 'ATTENDANCE_UPDATED':
        this.attendanceUpdated.update(val => val + 1);
        break;
      default:
        console.warn(`Unrecognized Orchestrator event type: ${event.event_type}`);
    }
  }
}
