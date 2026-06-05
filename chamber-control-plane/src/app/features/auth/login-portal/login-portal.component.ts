import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { CardModule } from 'primeng/card';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login-portal',
  standalone: true,
  imports: [
    CommonModule, 
    ReactiveFormsModule, 
    CardModule, 
    InputTextModule, 
    PasswordModule, 
    ButtonModule, 
    ToastModule
  ],
  providers: [MessageService],
  templateUrl: './login-portal.component.html',
  styleUrls: ['./login-portal.component.scss']
})
export class LoginPortalComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly messageService = inject(MessageService);

  loginForm: FormGroup = this.fb.group({
    username: ['', Validators.required],
    password: ['', Validators.required]
  });

  isLoading = false;

  onSubmit() {
    if (this.loginForm.invalid) {
      return;
    }

    this.isLoading = true;
    this.loginForm.disable();

    this.authService.login(this.loginForm.value).subscribe({
      next: () => {
        // Router navigation handled by AuthService
      },
      error: (err) => {
        this.isLoading = false;
        this.loginForm.enable();
        
        let errorMsg = 'An unexpected error occurred.';
        if (err.status === 401 || err.status === 403) {
          errorMsg = 'Invalid operator credentials.';
        }

        this.messageService.add({
          severity: 'error',
          summary: 'Authentication Failed',
          detail: errorMsg
        });
      }
    });
  }
}
