import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AdminService } from '../../core/services/admin.service';
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
        this.messageService.add({ severity: 'error', summary: 'Data Fetch Error', detail: 'Could not load legislators data.' });
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
        this.messageService.add({ severity: 'error', summary: 'Regeneration Failed', detail: err.error?.detail || 'Failed to regenerate token.' });
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
      message: 'CRITICAL WARNING: This will permanently revoke the device token and cryptographically purge the tablet. The legislator will be unable to vote. Proceed?',
      header: 'Confirm Device Wipe',
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
        this.messageService.add({ severity: 'success', summary: 'Device Wiped', detail: 'The hardware token has been revoked.' });
        this.loadLegislators();
      },
      error: (err) => {
        this.messageService.add({ severity: 'error', summary: 'Wipe Failed', detail: err.error?.detail || 'Failed to wipe the device.' });
      }
    });
  }
}
