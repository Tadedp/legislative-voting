import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const secureReq = req.clone({
    withCredentials: true
  });

  const router = inject(Router);

  return next(secureReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 || error.status === 403) {
        console.warn(`Security Event: HTTP ${error.status} intercepted. Evicting operator state.`);
        router.navigate(['/auth/login']);
      }
      return throwError(() => error);
    })
  );
};
