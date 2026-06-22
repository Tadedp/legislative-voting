import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'audit/sessions/:id',
    loadComponent: () => import('./features/public-audit/audit-shell/audit-shell.component').then(m => m.AuditShellComponent)
  },
  {
    path: '',
    redirectTo: '/audit/sessions/sample', // Default route for transparency portal root
    pathMatch: 'full'
  }
];
