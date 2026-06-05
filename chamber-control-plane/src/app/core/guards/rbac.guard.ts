import { CanMatchFn, Route, UrlSegment, Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

export const rbacGuard = (allowedRoles: string[]): CanMatchFn => {
  return (route: Route, _segments: UrlSegment[]) => {
    const authService = inject(AuthService);
    const router = inject(Router);
    
    const user = authService.currentUser();
    const currentRole = user ? user.role : null;

    if (currentRole && allowedRoles.includes(currentRole)) {
      return true;
    }

    console.error(`RBAC Violation: Role ${currentRole} denied access to path /${route.path}`);
    router.navigate(['/auth/login'], { queryParams: { unauthorized: true } });
    return false;
  };
};
