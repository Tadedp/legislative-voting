import { Component, Input, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';
import { TabsModule } from 'primeng/tabs';
import { InputTextModule } from 'primeng/inputtext';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-secret-ledger',
  standalone: true,
  imports: [CommonModule, TableModule, TabsModule, InputTextModule, IconFieldModule, InputIconModule, FormsModule],
  template: `
    <div class="card bg-white p-6 shadow-md rounded-xl">
      <h3 class="text-xl font-bold mb-4 text-gray-800">Auditoría de Votación Secreta (Decoupled Ledgers)</h3>
      
      <p-tabs value="0">
        <p-tablist>
            <p-tab value="0">Padrón Criptográfico (Eligibility)</p-tab>
            <p-tab value="1">Escrutinio Anónimo (Tally)</p-tab>
        </p-tablist>
        
        <p-tabpanels>
          <!-- TAB 1: ELIGIBILITY TREE -->
          <p-tabpanel value="0">
            <p class="mb-4 text-sm text-gray-600">Demuestra matemáticamente <strong>quién</strong> participó en la votación, verificando sus firmas emitidas por el hardware de las bancas.</p>
            <p-table [value]="participants" [paginator]="true" [rows]="10" styleClass="p-datatable-striped">
              <ng-template pTemplate="header">
                <tr>
                  <th>Legislador</th>
                  <th>Firma Criptográfica (Truncada)</th>
                  <th>Timestamp</th>
                </tr>
              </ng-template>
              <ng-template pTemplate="body" let-participant>
                <tr>
                  <td class="font-medium">{{ participant.legislator_name }}</td>
                  <td class="font-mono text-xs text-gray-500" title="{{participant.signature}}">
                    {{ participant.signature | slice:0:16 }}...{{ participant.signature | slice:-16 }}
                  </td>
                  <td class="text-sm text-gray-600">{{ participant.timestamp | date:'shortTime' }}</td>
                </tr>
              </ng-template>
            </p-table>
          </p-tabpanel>

          <!-- TAB 2: TALLY TREE & INDIVIDUAL RECEIPT -->
          <p-tabpanel value="1">
            <p class="mb-4 text-sm text-gray-600">Demuestra <strong>qué</strong> valores fueron emitidos. Ingrese el Hash (SHA-256) de su Llave Pública Efímera para verificar que su voto fue incluido en la raíz de Merkle.</p>
            
            <div class="mb-4">
              <p-iconField iconPosition="left">
                  <p-inputIcon styleClass="pi pi-search" />
                  <input type="text" pInputText placeholder="Ingrese su Hash SHA-256 (ej. a7f9b2c4...)" 
                         [ngModel]="searchHash()" (ngModelChange)="searchHash.set($event)" 
                         class="w-full md:w-96 font-mono text-sm" />
              </p-iconField>
            </div>
            
            <div *ngIf="tieBreaker" class="mb-4 bg-purple-50 p-4 rounded-lg border border-purple-200">
              <h4 class="text-purple-900 font-bold mb-1"><i class="pi pi-star-fill mr-2"></i>Voto Desempate Público (Presidencia)</h4>
              <p class="text-sm text-purple-700 mb-2">El presidente emitió el voto decisivo. Su firma criptográfica se incluyó en la raíz.</p>
              <div class="flex justify-between items-center bg-white p-3 rounded border border-purple-100 shadow-sm">
                <span class="font-medium text-purple-900">{{ tieBreaker.legislator_name }}</span>
                <span class="px-3 py-1 rounded text-sm font-bold bg-purple-200 text-purple-900">{{ tieBreaker.value }}</span>
              </div>
            </div>

            <p-table [value]="filteredTallies()" [paginator]="true" [rows]="10" styleClass="p-datatable-striped">
              <ng-template pTemplate="header">
                <tr>
                  <th>Voto Emitido</th>
                  <th>Hash Efímero (Truncado)</th>
                </tr>
              </ng-template>
              <ng-template pTemplate="body" let-tally>
                <tr [ngClass]="{'bg-yellow-100 border-2 border-yellow-400': searchHash() && tally.ephemeralHash.includes(searchHash())}">
                  <td>
                    <span class="px-2 py-1 rounded text-sm font-bold"
                      [ngClass]="{
                        'bg-green-100 text-green-800': tally.value === 'AFFIRMATIVE',
                        'bg-red-100 text-red-800': tally.value === 'NEGATIVE',
                        'bg-yellow-100 text-yellow-800': tally.value === 'ABSTENTION'
                      }">
                      {{ tally.value }}
                    </span>
                  </td>
                  <td class="font-mono text-xs" [ngClass]="searchHash() && tally.ephemeralHash.includes(searchHash()) ? 'text-gray-900 font-bold' : 'text-gray-500'">
                    {{ searchHash() && tally.ephemeralHash.includes(searchHash()) ? tally.ephemeralHash : (tally.ephemeralHash | slice:0:8) + '...' + (tally.ephemeralHash | slice:-8) }}
                  </td>
                </tr>
              </ng-template>
              <ng-template pTemplate="emptymessage">
                <tr>
                  <td colspan="2" class="text-center p-4">No se encontraron votos que coincidan.</td>
                </tr>
              </ng-template>
            </p-table>
          </p-tabpanel>
        </p-tabpanels>
      </p-tabs>
    </div>
  `
})
export class SecretLedgerComponent {
  @Input() participants: any[] = [];
  @Input() tallies: any[] = [];
  @Input() tieBreaker: any = null;

  searchHash = signal<string>('');

  filteredTallies = computed(() => {
    const term = this.searchHash().trim().toLowerCase();
    if (!term) return this.tallies;
    
    // Ensure the matched row stays visible or is pushed to top.
    const matched = this.tallies.filter(t => t.ephemeralHash.toLowerCase().includes(term));
    const unmatched = this.tallies.filter(t => !t.ephemeralHash.toLowerCase().includes(term));
    return [...matched, ...unmatched];
  });
}
