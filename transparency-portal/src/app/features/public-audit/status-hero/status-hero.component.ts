import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { VerificationResult } from '../../../core/services/audit-verification.service';
import { ProgressBarModule } from 'primeng/progressbar';
import { MessageModule } from 'primeng/message';
import { TooltipModule } from 'primeng/tooltip';

@Component({
  selector: 'app-status-hero',
  standalone: true,
  imports: [CommonModule, ProgressBarModule, MessageModule, TooltipModule],
  template: `
    <div class="card p-6 bg-white shadow-md rounded-xl">
      <h2 class="text-xl font-semibold mb-4">Estado de Verificación</h2>
      
      <div *ngIf="auditState === 'IDLE'" class="text-gray-500">
        Esperando snapshot...
      </div>

      <div *ngIf="auditState === 'VERIFYING'">
        <div class="flex items-center mb-2">
          <i class="pi pi-spin pi-spinner mr-2 text-blue-500"></i>
          <span class="text-blue-600 font-medium">Reconstruyendo Merkle Trees y Verificando Firmas Criptográficas...</span>
        </div>
        <p-progressBar [value]="progress"></p-progressBar>
      </div>

      <div *ngIf="auditState === 'VERIFIED'">
        <p-message severity="success" text="VERIFICADO: Integridad Matemática Garantizada." styleClass="w-full justify-start text-lg"></p-message>
        
        <div *ngIf="details && !details.isNominal && details.eligibilityCount !== undefined && details.anonymousTallyCount !== undefined" class="mt-4">
          <div *ngIf="details.eligibilityCount >= details.anonymousTallyCount" 
               class="bg-green-600 text-white p-3 rounded shadow-md font-semibold text-center flex items-center justify-center cursor-help"
               pTooltip="Las diferencias ocurren si legisladores se acreditan (Fase 1) pero no emiten su voto (Inacción Física). La integridad se mantiene siempre que Tokens >= Votos." 
               tooltipPosition="bottom">
            <i class="pi pi-shield mr-2 text-xl"></i> Integridad del Sistema: 0 votos forjados detectados ({{ details.anonymousTallyCount }} votos anónimos / {{ details.eligibilityCount }} acreditaciones)
          </div>
          <div *ngIf="details.eligibilityCount < details.anonymousTallyCount" 
               class="bg-red-600 text-white p-3 rounded shadow-md font-semibold text-center flex items-center justify-center">
            <i class="pi pi-times-circle mr-2 text-xl"></i> VIOLACIÓN DE INTEGRIDAD: Más votos en urna ({{ details.anonymousTallyCount }}) que acreditaciones ({{ details.eligibilityCount }}).
          </div>
          <div *ngIf="details.hasTieBreaker" class="mt-2 bg-blue-600 text-white p-2 rounded shadow-md font-semibold text-center flex items-center justify-center">
            <i class="pi pi-info-circle mr-2 text-lg"></i> Voto de Desempate (Público) inyectado exitosamente en la urna.
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm bg-green-50 p-4 rounded-lg border border-green-200" *ngIf="details">
          <div *ngIf="details.isNominal">
            <strong>Raíz Nominal Reconstruida:</strong> <br> <span class="font-mono text-xs break-all">{{ details.nominalRoot }}</span>
          </div>
          <div *ngIf="!details.isNominal">
            <strong>Raíz de Conteo (Tally Root):</strong> <br> <span class="font-mono text-xs break-all">{{ details.tallyRoot }}</span><br><br>
            <strong>Raíz de Elegibilidad:</strong> <br> <span class="font-mono text-xs break-all">{{ details.eligibilityRoot }}</span>
          </div>
        </div>
      </div>

      <div *ngIf="auditState === 'FAILED'">
        <p-message severity="error" text="FALLIDO: Integridad Comprometida." styleClass="w-full justify-start text-lg"></p-message>
        <div class="mt-4 text-sm bg-red-50 p-4 rounded-lg border border-red-200" *ngIf="details">
          <strong class="text-red-800">Causa del fallo:</strong>
          <p class="text-red-700 font-mono mt-2">{{ details.errorLog }}</p>
        </div>
      </div>
    </div>
  `
})
export class StatusHeroComponent {
  @Input() auditState: 'IDLE' | 'VERIFYING' | 'VERIFIED' | 'FAILED' = 'IDLE';
  @Input() progress: number = 0;
  @Input() details: VerificationResult | null = null;
}
