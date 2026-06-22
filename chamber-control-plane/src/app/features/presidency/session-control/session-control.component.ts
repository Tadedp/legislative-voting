import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { StateSyncService } from '../../../core/services/state-sync.service';
import { PresidencyService } from '../../../core/services/presidency.service';
import { SessionStatus } from '../../../core/models/orchestrator.models';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-session-control',
  standalone: true,
  imports: [
    CommonModule, FormsModule, ButtonModule, ConfirmDialogModule, 
    ToastModule, DialogModule, InputTextModule, SelectModule
  ],
  providers: [ConfirmationService, MessageService],
  templateUrl: './session-control.component.html',
  styleUrls: ['./session-control.component.scss']
})
export class SessionControlComponent implements OnInit {
  readonly stateSync = inject(StateSyncService);
  private readonly presidencyService = inject(PresidencyService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);
  private readonly auth = inject(AuthService);

  displayCreateDialog = false;
  newSessionTitle = '';
  newSessionPresType: 'EX_OFFICIO' | 'LEGISLATOR' = 'EX_OFFICIO';
  
  legislators: any[] = [];
  selectedLegislatorId: string | null = null;

  presTypeOptions = [
    { label: 'Ex-Officio (No vota, solo desempata)', value: 'EX_OFFICIO' },
    { label: 'Legislador (Vota y da quórum)', value: 'LEGISLATOR' }
  ];

  ngOnInit() {
    this.presidencyService.getLegislators().subscribe({
      next: (data) => this.legislators = data,
      error: () => console.error('Failed to load legislators')
    });
  }

  showCreateDialog() {
    this.newSessionTitle = '';
    this.newSessionPresType = 'EX_OFFICIO';
    this.selectedLegislatorId = null;
    this.displayCreateDialog = true;
  }

  createSession() {
    if (!this.newSessionTitle.trim()) {
      this.messageService.add({ severity: 'warn', summary: 'Atención', detail: 'El título es obligatorio.' });
      return;
    }

    if (this.newSessionPresType === 'LEGISLATOR' && !this.selectedLegislatorId) {
      this.messageService.add({ severity: 'warn', summary: 'Atención', detail: 'Debe seleccionar un legislador.' });
      return;
    }

    const payload = {
      title: this.newSessionTitle,
      pres_type: this.newSessionPresType,
      presiding_officer_id: this.newSessionPresType === 'LEGISLATOR' ? (this.selectedLegislatorId ?? undefined) : undefined
    };

    this.presidencyService.createSession(payload).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Éxito', detail: 'Sesión creada correctamente.' });
        this.displayCreateDialog = false;
        // Trigger rehydration to fetch the new PENDING session
        this.stateSync.rehydrateState();
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo crear la sesión.' });
      }
    });
  }

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
        const detail = err?.error?.detail || 'No se pudo cambiar el estado de la sesión.';
        this.messageService.add({ severity: 'error', summary: 'Error', detail: detail });
      }
    });
  }
}
