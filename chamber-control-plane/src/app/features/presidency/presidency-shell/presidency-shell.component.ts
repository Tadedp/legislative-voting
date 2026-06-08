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

import { SessionControlComponent } from '../session-control/session-control.component';
import { VotingOperatorComponent } from '../voting-operator/voting-operator.component';

@Component({
  selector: 'app-presidency-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, MenubarModule, SelectModule, FormsModule, ButtonModule, ToastModule, SessionControlComponent, VotingOperatorComponent],
  providers: [MessageService],
  templateUrl: './presidency-shell.component.html',
  styleUrls: ['./presidency-shell.component.scss']
})
export class PresidencyShellComponent implements OnInit, OnDestroy {
  authService = inject(AuthService);
  router = inject(Router);

  currentTime = new Date();
  clockInterval: any;

  items: MenuItem[] = [];

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
