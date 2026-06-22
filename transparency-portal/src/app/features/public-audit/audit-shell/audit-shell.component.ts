import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuditVerificationService } from '../../../core/services/audit-verification.service';
import { StatusHeroComponent } from '../status-hero/status-hero.component';
import { DataViewComponent } from '../data-view/data-view.component';
import { NominalLedgerComponent } from '../nominal-ledger/nominal-ledger.component';
import { SecretLedgerComponent } from '../secret-ledger/secret-ledger.component';

@Component({
  selector: 'app-audit-shell',
  standalone: true,
  imports: [
    CommonModule,
    StatusHeroComponent,
    DataViewComponent,
    NominalLedgerComponent,
    SecretLedgerComponent
  ],
  template: `
    <div class="audit-container p-6 max-w-7xl mx-auto">
      <h1 class="text-3xl font-bold mb-6 text-gray-900">Portal de Transparencia Pública</h1>
      
      <!-- Hero Status -->
      <app-status-hero 
        [auditState]="auditService.auditState()" 
        [progress]="auditService.progress()"
        [details]="auditService.verificationDetails()">
      </app-status-hero>

      <ng-container *ngIf="snapshotData">
        <!-- Context Data -->
        <app-data-view class="mt-6 block" [snapshot]="snapshotData"></app-data-view>

        <!-- Ledgers -->
        <div class="mt-6" *ngIf="auditService.auditState() === 'VERIFIED' || auditService.auditState() === 'FAILED'">
          <app-nominal-ledger 
            *ngIf="snapshotData.is_nominal" 
            [votes]="snapshotData.nominal_votes">
          </app-nominal-ledger>

          <app-secret-ledger 
            *ngIf="!snapshotData.is_nominal" 
            [participants]="snapshotData.verified_participants"
            [tallies]="snapshotData.anonymous_votes">
          </app-secret-ledger>
        </div>
      </ng-container>
    </div>
  `
})
export class AuditShellComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private http = inject(HttpClient);
  public auditService = inject(AuditVerificationService);
  
  public snapshotData: any = null;

  ngOnInit() {
    const roundId = this.route.snapshot.paramMap.get('id');
    if (roundId) {
      this.fetchAndVerify(roundId);
    }
  }

  private fetchAndVerify(roundId: string) {
    this.http.get(`/api/public/audit/${roundId}`).subscribe({
      next: (data) => {
        this.snapshotData = data;
        this.auditService.verifyE2E(this.snapshotData);
      },
      error: (err) => {
        console.error('Failed to fetch snapshot', err);
      }
    });
  }
}
