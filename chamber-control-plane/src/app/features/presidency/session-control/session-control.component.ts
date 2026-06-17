import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { StateSyncService } from '../../../core/services/state-sync.service';
import { PresidencyService } from '../../../core/services/presidency.service';
import { SessionStatus } from '../../../core/models/orchestrator.models';

@Component({
  selector: 'app-session-control',
  standalone: true,
  imports: [CommonModule, ButtonModule, ConfirmDialogModule, ToastModule],
  providers: [ConfirmationService, MessageService],
  templateUrl: './session-control.component.html',
  styleUrls: ['./session-control.component.scss']
})
export class SessionControlComponent {
  readonly stateSync = inject(StateSyncService);
  private readonly presidencyService = inject(PresidencyService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);

  changeStatus(newStatus: SessionStatus, event: Event) {
    const session = this.stateSync.sessionState();
    if (!session) return;

    if (newStatus === 'CLOSED') {
      this.confirmationService.confirm({
        target: event.target as EventTarget,
        message: '¿Está seguro de que desea CERRAR oficialmente la sesión legislativa? Esta acción no se puede deshacer.',
        header: 'Confirmar Cierre de Sesión',
        icon: 'pi pi-exclamation-triangle',
        acceptButtonStyleClass: 'p-button-danger',
        rejectButtonStyleClass: 'p-button-text',
        accept: () => this.executeStatusChange(session.id, newStatus)
      });
    } else {
      this.executeStatusChange(session.id, newStatus);
    }
  }

  private executeStatusChange(sessionId: string, newStatus: SessionStatus) {
    this.presidencyService.updateSessionStatus(sessionId, newStatus).subscribe({
      next: () => {
        this.messageService.add({ severity: 'info', summary: 'Solicitado', detail: `Se solicitó la transición de sesión a ${newStatus}.` });
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cambiar el estado de la sesión.' });
      }
    });
  }
}
