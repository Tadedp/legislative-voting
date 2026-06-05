import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
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
  private readonly http = inject(HttpClient);

  enrollForm: FormGroup = this.fb.group({
    national_id: ['', [Validators.required, Validators.pattern('^\\d+$')]],
    full_name: ['', Validators.required],
    biometric_payload: ['', Validators.required],
    hardware_payload: ['', Validators.required]
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

    let parsedHardware: any;
    try {
      parsedHardware = JSON.parse(formValue.hardware_payload);
      
      if (!parsedHardware.hardware_id || !parsedHardware.certificate_chain) {
        throw new Error('Missing required hardware payload fields.');
      }
    } catch (e) {
      this.errorMessage = 'Invalid Hardware Payload signature or malformed JSON structure.';
      return;
    }

    const payload = {
      national_id: formValue.national_id,
      full_name: formValue.full_name,
      hardware_id: parsedHardware.hardware_id,
      biometric_payload: formValue.biometric_payload,
      certificate_chain: parsedHardware.certificate_chain
    };

    this.isLoading = true;
    this.enrollForm.disable();

    this.http.post<any>('/legislators/enroll', payload).subscribe({
      next: (res) => {
        this.isLoading = false;
        this.enrollForm.enable();
        this.enrollForm.reset();
        
        // Display securely to the Admin
        this.generatedToken = res.device_token;
        this.showTokenDialog = true;
      },
      error: (err) => {
        this.isLoading = false;
        this.enrollForm.enable();
        
        this.errorMessage = err.error?.detail || 'An error occurred during enrollment.';
      }
    });
  }

  closeTokenDialog() {
    this.showTokenDialog = false;
    this.generatedToken = '';
  }
}
