import { Injectable, inject, DestroyRef, signal, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { retry, timer, Subscription } from 'rxjs';
import { 
  LegislativeSession, 
  ActiveAgendaItem, 
  ActiveVotingRound, 
  OrchestratorEvent, 
  CurrentStateResponse 
} from '../models/orchestrator.models';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class StateSyncService {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly auth = inject(AuthService);
  
  private socket$?: WebSocketSubject<OrchestratorEvent>;

  // Exclusive owner of application state
  readonly sessionState = signal<LegislativeSession | null>(null);
  readonly activeItem = signal<ActiveAgendaItem | null>(null);
  readonly votingRound = signal<ActiveVotingRound | null>(null);
  readonly isConnectionStable = signal<boolean>(false);

  private eventBuffer: OrchestratorEvent[] = [];
  private rehydrationSub?: Subscription;
  
  // Terminal states array for race condition guards
  private readonly terminalStates = ['RESOLVED', 'TIED', 'ABORTED', 'VOIDED'];

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      if (user) {
        if (!this.socket$ || this.socket$.closed) {
          this.initializeWebSocket();
        }
      } else {
        this.disconnectWebSocket();
      }
    });
  }

  private disconnectWebSocket() {
    if (this.socket$) {
      this.socket$.complete();
      this.socket$ = undefined;
    }
    if (this.rehydrationSub) {
      this.rehydrationSub.unsubscribe();
      this.rehydrationSub = undefined;
    }
  }

  private initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // When using proxy in dev server, window.location.host is localhost:4200
    const wsUrl = `${protocol}//${window.location.host}/ws/state`;

    this.socket$ = webSocket<OrchestratorEvent>({
      url: wsUrl,
      openObserver: {
        next: () => this.onConnectionEstablished()
      },
      closeObserver: {
        next: () => this.onConnectionLost()
      }
    });

    this.socket$
      .pipe(
        retry({
          count: Infinity,
          delay: (error, retryCount) => {
            console.warn(`WebSocket connection failed. Retrying in ${Math.min(1000 * Math.pow(2, retryCount), 30000)}ms...`);
            return timer(Math.min(1000 * Math.pow(2, retryCount), 30000));
          }
        }),
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
  }

  rehydrateState() {
    if (this.rehydrationSub) {
      this.rehydrationSub.unsubscribe();
    }

    this.rehydrationSub = this.http.get<CurrentStateResponse>('/legislative-sessions/current')
      .pipe(
        retry({
          count: Infinity,
          delay: (error, retryCount) => {
            if (error.status === 404) throw error;
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
          if (err.status === 404) {
            // A 404 means there is no active legislative session yet.
            // This is a normal state. We must unlock the UI so the Presidency can start one.
            this.sessionState.set(null);
            this.activeItem.set(null);
            this.votingRound.set(null);
            this.isConnectionStable.set(true);
            this.eventBuffer = [];
          }
        }
      });
  }

  private handleEvent(event: OrchestratorEvent, isReplaying: boolean = false) {
    if (!event || !event.event_type) return;

    if (!this.isConnectionStable() && !isReplaying) {
      if (this.eventBuffer.length < 1000) {
        this.eventBuffer.push(event);
      } else {
        console.warn('Event buffer overflow. Dropping event.');
      }
      return;
    }

    switch (event.event_type) {
      case 'SESSION_STATUS_CHANGED':
        this.sessionState.set(event.data);
        break;
      case 'AGENDA_ITEM_UPDATED':
        this.activeItem.set(event.data);
        break;
      case 'VOTING_ROUND_OPENED':
        this.votingRound.set(event.data);
        break;
      case 'VOTING_ROUND_CLOSED':
        // The backend payload only has ids, so we merge the state manually
        this.votingRound.update(current => {
          if (current && this.terminalStates.includes(current.status)) return current;
          return current ? { ...current, status: 'VOTING_CLOSED' } : null;
        });
        break;
      case 'VOTING_ROUND_TIED':
        this.votingRound.update(current => current ? { ...current, status: 'TIED' } : null);
        break;
      case 'VOTING_ROUND_RESOLVED':
        this.votingRound.update(current => current ? { ...current, status: 'RESOLVED' } : null);
        break;
      case 'VOTING_ROUND_ABORTED':
        // Void the round entirely so the President can start over
        this.votingRound.set(null);
        break;
      case 'VOTE_CAST':
        // Placeholder for future vote tally implementation
        break;
      case 'QUORUM_WARNING':
        console.warn(`Quorum warning received: ${event.data?.connected}/${event.data?.minimum_required}`);
        break;
      default:
        console.warn(`Unrecognized Orchestrator event type: ${event.event_type}`);
    }
  }
}
