import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AdminService } from '../../../core/services/admin.service';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';

import { DialogModule } from 'primeng/dialog';

@Component({
  selector: 'app-device-management',
  standalone: true,
  imports: [CommonModule, TableModule, ButtonModule, ConfirmDialogModule, ToastModule, DialogModule],
  providers: [ConfirmationService, MessageService],
  templateUrl: './device-management.component.html',
  styleUrls: ['./device-management.component.scss']
})
export class DeviceManagementComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);

  legislators: any[] = [];
  isLoading = false;
  
  showTokenDialog = false;
  generatedToken = '';

  ngOnInit() {
    this.loadLegislators();
  }

  loadLegislators() {
    this.isLoading = true;
    this.adminService.getLegislators().subscribe({
      next: (data) => {
        this.legislators = data;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Error de Carga', detail: 'No se pudieron cargar los datos de los legisladores.' });
      }
    });
  }

  regenerateToken(legislatorId: string) {
    this.isLoading = true;
    this.adminService.regenerateProvisioningToken(legislatorId).subscribe({
      next: (res) => {
        this.isLoading = false;
        this.generatedToken = res.provisioning_token;
        this.showTokenDialog = true;
        this.loadLegislators();
      },
      error: (err) => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Fallo en Regeneración', detail: err.error?.detail || 'Fallo al regenerar el token.' });
      }
    });
  }
  
  closeTokenDialog() {
    this.showTokenDialog = false;
    this.generatedToken = '';
  }

  confirmWipe(event: Event, deviceId: string) {
    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: 'ADVERTENCIA CRÍTICA: Esto revocará permanentemente el token de la terminal y la purgará criptográficamente. El legislador no podrá votar. ¿Proceder?',
      header: 'Confirmar Desvinculación de Terminal',
      icon: 'pi pi-exclamation-triangle',
      acceptIcon: "none",
      rejectIcon: "none",
      rejectButtonStyleClass: "p-button-text",
      acceptButtonStyleClass: "p-button-danger",
      accept: () => {
        this.wipeDevice(deviceId);
      }
    });
  }

  private wipeDevice(deviceId: string) {
    this.adminService.wipeDevice(deviceId).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Terminal Desvinculada', detail: 'El token de hardware ha sido revocado.' });
        this.loadLegislators();
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Fallo al Desvincular', detail: err.error?.detail || 'Fallo al desvincular la terminal.' });
      }
    });
  }
}
