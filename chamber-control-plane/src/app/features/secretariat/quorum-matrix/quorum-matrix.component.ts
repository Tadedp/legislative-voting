import { Component, inject, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableModule } from 'primeng/table';
import { SelectButtonModule } from 'primeng/selectbutton';
import { MessageModule } from 'primeng/message';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { StateSyncService } from '../../../core/services/state-sync.service';
import { SecretariatService, SessionAttendanceEnriched } from '../../../core/services/secretariat.service';

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

  // Computed signal to determine if the matrix is locked
  readonly isVotingOpen = computed(() => this.stateSync.votingRound()?.status === 'VOTING_OPEN');
  
  attendanceList: SessionAttendanceEnriched[] = [];
  isLoading = false;

  statusOptions = [
    { label: 'Present', value: 'PRESENT' },
    { label: 'Absent', value: 'ABSENT' }
  ];

  constructor() {
    // Whenever the session changes, reload the attendance
    effect(() => {
      const session = this.stateSync.sessionState();
      if (session) {
        this.loadAttendance(session.id);
      } else {
        this.attendanceList = [];
      }
    });
  }

  loadAttendance(sessionId: string) {
    this.isLoading = true;
    this.secretariatService.getSessionAttendance(sessionId).subscribe({
      next: (data) => {
        this.attendanceList = data;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not load quorum matrix.' });
      }
    });
  }

  onStatusChange(record: SessionAttendanceEnriched) {
    // If the system is locked physically by a voting round, revert and ignore
    if (this.isVotingOpen()) {
      return;
    }

    const session = this.stateSync.sessionState();
    if (!session) return;

    this.secretariatService.updateAttendance(session.id, record.legislator_id, record.status as any).subscribe({
      next: () => {
        this.messageService.add({ 
          severity: 'success', 
          summary: 'Attendance Updated', 
          detail: `${record.full_name} marked as ${record.status}` 
        });
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Update Failed', detail: 'Could not update attendance status.' });
        // Revert the local change
        this.loadAttendance(session.id);
      }
    });
  }
}
