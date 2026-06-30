import { Component, inject, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { toObservable } from '@angular/core/rxjs-interop';
import { switchMap, filter, concatMap, catchError } from 'rxjs/operators';
import { EMPTY, retry } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService, MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';
import { SelectModule } from 'primeng/select';
import { InputTextModule } from 'primeng/inputtext';
import { CheckboxModule } from 'primeng/checkbox';
import { InputNumberModule } from 'primeng/inputnumber';
import { MessageModule } from 'primeng/message';
import { StateSyncService } from '../../../core/services/state-sync.service';
import { PresidencyService, VotingType, VotingTally } from '../../../core/services/presidency.service';

@Component({
  selector: 'app-voting-operator',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule, ButtonModule, ConfirmDialogModule, ToastModule, 
    SelectModule, InputTextModule, CheckboxModule, InputNumberModule, MessageModule
  ],
  providers: [ConfirmationService, MessageService],
  templateUrl: './voting-operator.component.html',
  styleUrls: ['./voting-operator.component.scss']
})
export class VotingOperatorComponent {
  readonly stateSync = inject(StateSyncService);
  private readonly presidencyService = inject(PresidencyService);
  private readonly confirmationService = inject(ConfirmationService);
  private readonly messageService = inject(MessageService);
  private readonly fb = inject(FormBuilder);

  // Core Computed State
  readonly hasActiveRound = computed(() => !!this.stateSync.votingRound());
  readonly roundStatus = computed(() => this.stateSync.votingRound()?.status);
  
  // Tally State
  readonly currentTally = signal<VotingTally | null>(null);

  // Form
  createForm: FormGroup;
  votingTypes: VotingType[] = [];
  
  stageOptions = [
    { label: 'Única', value: 'SINGLE' },
    { label: 'En General', value: 'GENERAL' },
    { label: 'En Particular', value: 'SPECIFIC' }
  ];

  isCreating = false;

  constructor() {
    this.createForm = this.fb.group({
      stage: ['SINGLE', Validators.required],
      voting_type_id: ['', Validators.required],
      specific_reference: [''],
      is_nominal: [true],
      president_votes_ordinarily: [false],
      time_limit_seconds: [null]
    });

    // Handle conditional specific_reference validator
    this.createForm.get('stage')?.valueChanges.subscribe(val => {
      const specificCtrl = this.createForm.get('specific_reference');
      if (val === 'SPECIFIC') {
        specificCtrl?.setValidators([Validators.required]);
      } else {
        specificCtrl?.clearValidators();
      }
      specificCtrl?.updateValueAndValidity();
    });

    this.loadVotingTypes();

    // Reactive Tally Fetching
    toObservable(this.stateSync.votingRound).pipe(
      filter(round => round?.status === 'VOTING_CLOSED'),
      switchMap(round => this.presidencyService.getRoundTally(round!.id).pipe(
        retry({ count: 5, delay: 1000 }),
        catchError(() => {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo obtener el escrutinio.' });
          return EMPTY;
        })
      ))
    ).subscribe({
      next: (tally) => {
        if (tally) {
          this.currentTally.set(tally);
        }
      }
    });
  }

  loadVotingTypes() {
    this.presidencyService.getVotingTypes().subscribe({
      next: (types) => this.votingTypes = types,
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Fallo al cargar tipos de votación.' })
    });
  }

  // --- STATE 0: CREATION ---
  initiateVotingRound() {
    if (this.createForm.invalid) return;
    
    const session = this.stateSync.sessionState();
    const activeItem = this.stateSync.activeItem();
    if (!session || !activeItem) {
      this.messageService.add({ severity: 'warn', summary: 'Contexto Faltante', detail: 'Se requiere una sesión activa y un tema de agenda.' });
      return;
    }

    this.isCreating = true;
    const payload = {
      ...this.createForm.value,
      agenda_item_id: activeItem.id
    };

    // Chain Creation -> Open to prevent race conditions
    this.presidencyService.createVotingRound(session.id, payload).pipe(
      concatMap(response => this.presidencyService.openVotingRound(response.id))
    ).subscribe({
      next: () => {
        this.isCreating = false;
        this.messageService.add({ severity: 'success', summary: 'Votación Abierta', detail: 'La votación está activa en el recinto.' });
        this.createForm.reset({ stage: 'SINGLE', is_nominal: true, president_votes_ordinarily: false });
      },
      error: (err) => {
        this.isCreating = false;
        // Use backend error message if available
        const detail = err.error?.detail || 'No se pudo iniciar la votación.';
        this.messageService.add({ severity: 'error', summary: 'Operación Fallida', detail });
      }
    });
  }

  // --- STATE 1: CLOSURE ---
  closeVoting(event: Event) {
    const round = this.stateSync.votingRound();
    if (!round) return;

    const tokensIssued = this.stateSync.tokensIssued();
    const votesReceived = this.stateSync.votesReceived();

    const isRaceCondition = votesReceived < tokensIssued;
    
    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: isRaceCondition 
        ? 'Atención: Hay legisladores autorizados que aún no han emitido su voto. ¿Desea cerrar la urna de todos modos?'
        : '¿Está seguro de que desea cerrar la votación?',
      header: 'Cerrar Votación',
      icon: 'pi pi-exclamation-triangle',
      acceptButtonStyleClass: isRaceCondition ? 'p-button-danger' : 'p-button-warning',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        this.presidencyService.closeVotingRound(round.id).subscribe({
          next: () => {
             // UI purely waits for WebSocket VOTING_ROUND_CLOSED
             this.messageService.add({ severity: 'info', summary: 'Cerrando', detail: 'Señalizando el bloqueo a las terminales...' });
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo cerrar la votación.' })
        });
      }
    });
  }

  // --- STATE 2 & 3: PROCLAMATION & RECTIFICATION ---
  proclaimVoting(event: Event) {
    const round = this.stateSync.votingRound();
    const tally = this.currentTally();
    if (!round || !tally) return;

    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: '¿Está seguro de que desea proclamar este resultado? Quedará registrado permanentemente.',
      header: 'Proclamar Resultado',
      icon: 'pi pi-check-circle',
      acceptButtonStyleClass: 'p-button-success',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        this.presidencyService.proclaimVotingRound(round.id).subscribe({
          next: () => {
            this.messageService.add({ severity: 'success', summary: 'Proclamado', detail: 'El voto ha sido cimentado legalmente.' });
            this.currentTally.set(null); // Clear local tally
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo proclamar la votación.' })
        });
      }
    });
  }

  rectifyVoting(event: Event) {
    const round = this.stateSync.votingRound();
    if (!round) return;

    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: '¿Está seguro de que desea ANULAR esta votación? Se clonará un nuevo borrador.',
      header: 'Rectificar / Anular Votación',
      icon: 'pi pi-exclamation-triangle',
      acceptButtonStyleClass: 'p-button-danger',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        this.presidencyService.rectifyVotingRound(round.id).subscribe({
          next: (newRound) => {
            this.messageService.add({ severity: 'warn', summary: 'Rectificado', detail: 'Votación anulada exitosamente.' });
            this.currentTally.set(null);
            this.stateSync.votingRound.set(null);
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'No se pudo rectificar la votación.' })
        });
      }
    });
  }
}
