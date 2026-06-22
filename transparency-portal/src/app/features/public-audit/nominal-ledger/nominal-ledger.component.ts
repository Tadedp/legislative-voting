import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableModule } from 'primeng/table';

@Component({
  selector: 'app-nominal-ledger',
  standalone: true,
  imports: [CommonModule, TableModule],
  template: `
    <div class="card bg-white p-6 shadow-md rounded-xl">
      <h3 class="text-xl font-bold mb-4 text-gray-800">Registro Nominal Público</h3>
      <p-table [value]="votes" [paginator]="true" [rows]="10" styleClass="p-datatable-striped">
        <ng-template pTemplate="header">
          <tr>
            <th>Legislador</th>
            <th>Voto</th>
            <th>Firma Criptográfica (Truncada)</th>
            <th>Timestamp</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-vote>
          <tr>
            <td class="font-medium">{{ vote.legislator_name }}</td>
            <td>
              <span class="px-2 py-1 rounded text-sm font-bold"
                [ngClass]="{
                  'bg-green-100 text-green-800': vote.value === 'AFFIRMATIVE',
                  'bg-red-100 text-red-800': vote.value === 'NEGATIVE',
                  'bg-yellow-100 text-yellow-800': vote.value === 'ABSTENTION'
                }">
                {{ vote.value }}
              </span>
            </td>
            <td class="font-mono text-xs text-gray-500" title="{{vote.signature}}">
              {{ vote.signature | slice:0:16 }}...{{ vote.signature | slice:-16 }}
            </td>
            <td class="text-sm text-gray-600">{{ vote.timestamp | date:'shortTime' }}</td>
          </tr>
        </ng-template>
        <ng-template pTemplate="emptymessage">
          <tr>
            <td colspan="4" class="text-center p-4">No hay votos registrados.</td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class NominalLedgerComponent {
  @Input() votes: any[] = [];
}
