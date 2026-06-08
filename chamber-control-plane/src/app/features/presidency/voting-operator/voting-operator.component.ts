import { Component, inject, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { toObservable } from '@angular/core/rxjs-interop';
import { switchMap, filter, concatMap } from 'rxjs/operators';
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
    { label: 'Single', value: 'SINGLE' },
    { label: 'General', value: 'GENERAL' },
    { label: 'Specific', value: 'SPECIFIC' }
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
      switchMap(round => this.presidencyService.getRoundTally(round!.id))
    ).subscribe({
      next: (tally) => this.currentTally.set(tally),
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not fetch tally.' })
    });
  }

  loadVotingTypes() {
    this.presidencyService.getVotingTypes().subscribe({
      next: (types) => this.votingTypes = types,
      error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load voting types.' })
    });
  }

  // --- STATE 0: CREATION ---
  initiateVotingRound() {
    if (this.createForm.invalid) return;
    
    const session = this.stateSync.sessionState();
    const activeItem = this.stateSync.activeItem();
    if (!session || !activeItem) {
      this.messageService.add({ severity: 'warn', summary: 'Missing Context', detail: 'An active session and agenda item are required.' });
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
        this.messageService.add({ severity: 'success', summary: 'Voting Opened', detail: 'The round is now active on the floor.' });
        this.createForm.reset({ stage: 'SINGLE', is_nominal: true, president_votes_ordinarily: false });
      },
      error: (err) => {
        this.isCreating = false;
        // Use backend error message if available
        const detail = err.error?.detail || 'Could not initiate voting round.';
        this.messageService.add({ severity: 'error', summary: 'Operation Failed', detail });
      }
    });
  }

  // --- STATE 1: CLOSURE ---
  closeVoting(event: Event) {
    const round = this.stateSync.votingRound();
    if (!round) return;

    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: 'Are you sure you want to close the voting round?',
      header: 'Close Voting',
      icon: 'pi pi-exclamation-triangle',
      acceptButtonStyleClass: 'p-button-warning',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        this.presidencyService.closeVotingRound(round.id).subscribe({
          next: () => {
             // UI purely waits for WebSocket VOTING_ROUND_CLOSED
             this.messageService.add({ severity: 'info', summary: 'Closing', detail: 'Signaling edge devices to lock...' });
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not close the round.' })
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
      message: 'Are you sure you want to proclaim this result? It will be permanently recorded.',
      header: 'Proclaim Result',
      icon: 'pi pi-check-circle',
      acceptButtonStyleClass: 'p-button-success',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        const payload = {
          affirmative: tally.affirmative,
          negative: tally.negative,
          abstentions: tally.abstentions
        };

        this.presidencyService.proclaimVotingRound(round.id, payload).subscribe({
          next: () => {
            this.messageService.add({ severity: 'success', summary: 'Proclaimed', detail: 'The vote has been legally cemented.' });
            this.currentTally.set(null); // Clear local tally
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not proclaim round.' })
        });
      }
    });
  }

  rectifyVoting(event: Event) {
    const round = this.stateSync.votingRound();
    if (!round) return;

    this.confirmationService.confirm({
      target: event.target as EventTarget,
      message: 'Are you sure you want to VOID this round? A new draft round will be cloned.',
      header: 'Rectify / Abort Voting',
      icon: 'pi pi-exclamation-triangle',
      acceptButtonStyleClass: 'p-button-danger',
      rejectButtonStyleClass: 'p-button-text',
      accept: () => {
        this.presidencyService.rectifyVotingRound(round.id).subscribe({
          next: () => {
            this.messageService.add({ severity: 'warn', summary: 'Rectified', detail: 'Round voided successfully.' });
            this.currentTally.set(null);
          },
          error: () => this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not rectify round.' })
        });
      }
    });
  }
}
