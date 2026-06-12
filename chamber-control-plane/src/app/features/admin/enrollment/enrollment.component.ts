import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AdminService } from '../../core/services/admin.service';
import { CardModule } from 'primeng/card';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { DialogModule } from 'primeng/dialog';
import { MessageService } from 'primeng/api';

@Component({
  selector: 'app-enrollment',
  standalone: true,
  imports: [
    CommonModule, 
    ReactiveFormsModule, 
    CardModule, 
    InputTextModule, 
    TextareaModule, 
    ButtonModule, 
    MessageModule,
    DialogModule
  ],
  providers: [MessageService],
  templateUrl: './enrollment.component.html',
  styleUrls: ['./enrollment.component.scss']
})
export class EnrollmentComponent {
  private readonly fb = inject(FormBuilder);
  private readonly adminService = inject(AdminService);

  enrollForm: FormGroup = this.fb.group({
    national_id: ['', [Validators.required, Validators.pattern('^\\d+$')]],
    full_name: ['', Validators.required]
  });

  errorMessage: string | null = null;
  isLoading = false;
  
  // Dialog state for device token
  showTokenDialog = false;
  generatedToken = '';

  onSubmit() {
    if (this.enrollForm.invalid) {
      return;
    }

    this.errorMessage = null;
    const formValue = this.enrollForm.value;

    const payload = {
      national_id: formValue.national_id,
      full_name: formValue.full_name
    };

    this.isLoading = true;
    this.enrollForm.disable();

    this.adminService.createLegislator(payload).subscribe({
      next: (res) => {
        this.isLoading = false;
        this.enrollForm.enable();
        this.enrollForm.reset();
        
        // Display securely to the Admin
        this.generatedToken = res.provisioning_token;
        this.showTokenDialog = true;
      },
      error: (err) => {
        this.isLoading = false;
        this.enrollForm.enable();
        
        this.errorMessage = err.error?.detail || 'An error occurred during legislator creation.';
      }
    });
  }

  closeTokenDialog() {
    this.showTokenDialog = false;
    this.generatedToken = '';
  }
}
