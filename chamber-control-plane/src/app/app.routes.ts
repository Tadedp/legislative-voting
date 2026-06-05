import { Routes } from '@angular/router';
import { rbacGuard } from './core/guards/rbac.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'auth/login',
    pathMatch: 'full'
  },
  {
    path: 'auth/login',
    loadComponent: () => import('./features/auth/login-portal/login-portal.component').then(m => m.LoginPortalComponent)
  },
  {
    path: 'admin',
    loadComponent: () => import('./features/admin/admin-shell/admin-shell.component').then(m => m.AdminShellComponent),
    canMatch: [rbacGuard(['ADMIN'])],
    children: [
      { path: '', redirectTo: 'enrollment', pathMatch: 'full' },
      { path: 'enrollment', loadComponent: () => import('./features/admin/enrollment/enrollment.component').then(m => m.EnrollmentComponent) },
      { path: 'devices', loadComponent: () => import('./features/admin/device-management/device-management.component').then(m => m.DeviceManagementComponent) }
    ]
  },
  {
    path: 'presidency',
    loadComponent: () => import('./features/presidency/presidency-shell/presidency-shell.component').then(m => m.PresidencyShellComponent),
    canMatch: [rbacGuard(['PRESIDENCY'])]
  },
  {
    path: 'secretariat',
    loadComponent: () => import('./features/secretariat/secretariat-shell/secretariat-shell.component').then(m => m.SecretariatShellComponent),
    canMatch: [rbacGuard(['SECRETARY'])]
  },
  {
    path: '**',
    redirectTo: 'auth/login'
  }
];
