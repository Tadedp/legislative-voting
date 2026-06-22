import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-data-view',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 bg-gray-50 p-6 rounded-xl border border-gray-200 shadow-sm">
      <div>
        <span class="text-gray-500 text-sm font-semibold uppercase tracking-wider">Proyecto / Moción</span>
        <p class="mt-1 text-lg font-medium text-gray-900">{{ snapshot?.agenda_item_title }}</p>
      </div>
      <div>
        <span class="text-gray-500 text-sm font-semibold uppercase tracking-wider">Modalidad</span>
        <p class="mt-1 text-lg font-medium text-gray-900">
          <span class="px-3 py-1 rounded-full text-sm font-bold"
            [ngClass]="snapshot?.is_nominal ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'">
            {{ snapshot?.is_nominal ? 'Votación Nominal (Pública)' : 'Votación Secreta' }}
          </span>
        </p>
      </div>
      <div>
        <span class="text-gray-500 text-sm font-semibold uppercase tracking-wider">Fecha y Hora (UTC)</span>
        <p class="mt-1 text-lg font-medium text-gray-900">{{ snapshot?.timestamp | date:'medium' }}</p>
      </div>
    </div>
  `
})
export class DataViewComponent {
  @Input() snapshot: any;
}
