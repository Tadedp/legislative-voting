import { Component, inject, computed, effect, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableModule } from 'primeng/table';
import { SelectButtonModule } from 'primeng/selectbutton';
import { MessageModule } from 'primeng/message';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { StateSyncService } from '../../../core/services/state-sync.service';
import { SecretariatService, SessionAttendanceEnriched } from '../../../core/services/secretariat.service';
import { Subject, of } from 'rxjs';
import { concatMap, catchError, tap, debounceTime, switchMap } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

@Component({
  selector: 'app-quorum-matrix',
  standalone: true,
  imports: [CommonModule, FormsModule, TableModule, SelectButtonModule, MessageModule, ToastModule],
  providers: [MessageService],
  templateUrl: './quorum-matrix.component.html',
  styleUrls: ['./quorum-matrix.component.scss']
})
export class QuorumMatrixComponent {
  private readonly stateSync = inject(StateSyncService);
  private readonly secretariatService = inject(SecretariatService);
  private readonly messageService = inject(MessageService);
  private readonly destroyRef = inject(DestroyRef);

  // Computed signal to determine if the matrix is locked
  readonly isVotingOpen = computed(() => this.stateSync.votingRound()?.status === 'VOTING_OPEN');
  

  
  attendanceList: SessionAttendanceEnriched[] = [];
  isLoading = false;

  statusOptions = [
    { label: 'Presente', value: 'PRESENT' },
    { label: 'Ausente', value: 'ABSENT' }
  ];

  private updateSubject = new Subject<{record: SessionAttendanceEnriched, sessionId: string}>();
  private attendanceUpdate$ = new Subject<string>();

  constructor() {
    effect(() => {
      this.stateSync.attendanceUpdated();
      const session = this.stateSync.sessionState();
      if (session) {
        this.attendanceUpdate$.next(session.id);
      } else {
        this.attendanceList = [];
      }
    });

    this.attendanceUpdate$.pipe(
      tap(() => this.isLoading = true),
      debounceTime(500),
      switchMap(sessionId => this.secretariatService.getSessionAttendance(sessionId).pipe(
        catchError((err) => {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cargar la matriz de quórum.' });
          return of([]);
        })
      )),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe({
      next: (data) => {
        if (data.length > 0 || this.attendanceList.length === 0) {
            this.attendanceList = data;
        }
        this.isLoading = false;
      }
    });

    this.updateSubject.pipe(
      concatMap(({record, sessionId}) => 
        this.secretariatService.updateAttendance(sessionId, record.legislator_id, record.status as any).pipe(
          tap(() => {
            this.messageService.add({ 
              severity: 'success', 
              summary: 'Asistencia Actualizada', 
              detail: `${record.full_name} marcado como ${record.status}` 
            });
          }),
          catchError((err) => {
            this.messageService.add({ severity: 'error', summary: 'Fallo al Actualizar', detail: 'No se pudo actualizar el estado de asistencia.' });
            this.loadAttendance(sessionId);
            return of(null);
          })
        )
      ),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe();
  }

  loadAttendance(sessionId: string) {
    this.isLoading = true;
    this.attendanceUpdate$.next(sessionId);
  }

  onStatusChange(record: SessionAttendanceEnriched) {
    if (this.isVotingOpen()) {
      record.status = record.status === 'PRESENT' ? 'ABSENT' : 'PRESENT';
      this.messageService.add({ severity: 'warn', summary: 'Votación Activa', detail: 'No se puede modificar la asistencia durante una votación.' });
      return;
    }

    const session = this.stateSync.sessionState();
    if (!session) return;

    this.updateSubject.next({ record, sessionId: session.id });
  }
}
