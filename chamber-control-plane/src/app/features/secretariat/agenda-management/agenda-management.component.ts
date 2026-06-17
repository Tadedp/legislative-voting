import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TableModule } from 'primeng/table';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { SelectModule } from 'primeng/select';
import { DialogModule } from 'primeng/dialog';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { SecretariatService, AgendaItem } from '../../../core/services/secretariat.service';

@Component({
  selector: 'app-agenda-management',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, TableModule, ButtonModule, 
    InputTextModule, TextareaModule, SelectModule, DialogModule, ToastModule
  ],
  providers: [MessageService],
  templateUrl: './agenda-management.component.html',
  styleUrls: ['./agenda-management.component.scss']
})
export class AgendaManagementComponent implements OnInit {
  private readonly secretariatService = inject(SecretariatService);
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(FormBuilder);

  agendaItems: AgendaItem[] = [];
  isLoading = false;

  // Dialog State
  showDialog = false;
  isEditing = false;
  editingId: string | null = null;

  agendaForm: FormGroup;

  categoryOptions = [
    { label: 'Proyecto', value: 'PROJECT' },
    { label: 'Moción', value: 'MOTION' }
  ];

  constructor() {
    this.agendaForm = this.fb.group({
      category: ['PROJECT', Validators.required],
      file_number: ['', Validators.required],
      title: ['', Validators.required],
      summary: ['']
    });
  }

  ngOnInit() {
    this.loadAgenda();
  }

  loadAgenda() {
    this.isLoading = true;
    this.secretariatService.getAgendaItems().subscribe({
      next: (data) => {
        this.agendaItems = data;
        this.isLoading = false;
      },
      error: (err) => {
        this.isLoading = false;
        this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudieron cargar los temas de agenda.' });
      }
    });
  }

  openCreateDialog() {
    this.isEditing = false;
    this.editingId = null;
    this.agendaForm.reset({ category: 'PROJECT' });
    this.showDialog = true;
  }

  openEditDialog(item: AgendaItem) {
    this.isEditing = true;
    this.editingId = item.id;
    this.agendaForm.patchValue({
      category: item.category,
      file_number: item.file_number,
      title: item.title,
      summary: item.summary
    });
    this.showDialog = true;
  }

  saveItem() {
    if (this.agendaForm.invalid) return;

    const data = this.agendaForm.value;

    if (this.isEditing && this.editingId) {
      this.secretariatService.updateAgendaItem(this.editingId, data).subscribe({
        next: () => {
          this.showDialog = false;
          this.loadAgenda();
          this.messageService.add({ severity: 'success', summary: 'Éxito', detail: 'Tema de agenda actualizado.' });
        },
        error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo actualizar el tema.' })
      });
    } else {
      this.secretariatService.createAgendaItem(data).subscribe({
        next: () => {
          this.showDialog = false;
          this.loadAgenda();
          this.messageService.add({ severity: 'success', summary: 'Éxito', detail: 'Tema de agenda creado.' });
        },
        error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo crear el tema.' })
      });
    }
  }

  sendToFloor(item: AgendaItem) {
    this.secretariatService.updateAgendaItem(item.id, { status: 'DEBATE' }).subscribe({
      next: () => {
        this.messageService.add({ severity: 'success', summary: 'Enviado a Recinto', detail: `${item.title} está ahora en debate.` });
        this.loadAgenda();
      },
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo enviar el tema a recinto.' })
    });
  }
}
