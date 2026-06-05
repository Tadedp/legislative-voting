import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';

@Component({
  selector: 'app-device-management',
  standalone: true,
  imports: [CommonModule, TableModule, ButtonModule, ConfirmDialogModule, ToastModule],
  providers: [ConfirmationService, MessageService],
  templateUrl: './device-management.component.html',
  styleUrls: ['./device-management.component.scss']
})
export class DeviceManagementComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);

  legislators: any[] = [];
  isLoading = false;

  ngOnInit() {
    this.loadLegislators();
  }

  loadLegislators() {
    this.isLoading = true;
    this.http.get<any[]>('/legislators').subscribe({
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
    this.http.post(`/devices/${deviceId}/wipe`, {}).subscribe({
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
