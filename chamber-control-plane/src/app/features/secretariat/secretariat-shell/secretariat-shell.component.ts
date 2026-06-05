import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { MenubarModule } from 'primeng/menubar';
import { MenuItem } from 'primeng/api';
import { SelectModule } from 'primeng/select';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { AuthService } from '../../../core/services/auth.service';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';

@Component({
  selector: 'app-secretariat-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, MenubarModule, SelectModule, FormsModule, ButtonModule, ToastModule],
  providers: [MessageService],
  templateUrl: './secretariat-shell.component.html',
  styleUrls: ['./secretariat-shell.component.scss']
})
export class SecretariatShellComponent implements OnInit, OnDestroy {
  authService = inject(AuthService);
  router = inject(Router);

  currentTime = new Date();
  clockInterval: any;

  items: MenuItem[] = [
    { label: 'Attendance', icon: 'pi pi-check-square' },
    { label: 'Agenda Items', icon: 'pi pi-list' },
    { label: 'Read Tallies', icon: 'pi pi-eye' }
  ];

  ngOnInit() {
    this.clockInterval = setInterval(() => {
      this.currentTime = new Date();
    }, 1000);
  }

  ngOnDestroy() {
    if (this.clockInterval) {
      clearInterval(this.clockInterval);
    }
  }

  logout() {
    this.authService.logout();
  }
}
