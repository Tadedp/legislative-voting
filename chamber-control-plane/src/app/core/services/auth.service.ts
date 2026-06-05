import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';

export interface AuthRequest {
  username: string;
  password?: string;
}

export interface AuthResponse {
  id: string;
  username: string;
  role: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  // Expose current user globally
  readonly currentUser = signal<AuthResponse | null>(null);

  login(credentials: AuthRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>('/auth/login', credentials).pipe(
      tap((response) => {
        this.currentUser.set(response);
        
        // Route based on role
        if (response.role === 'ADMIN') {
          this.router.navigate(['/admin']);
        } else if (response.role === 'PRESIDENCY') {
          this.router.navigate(['/presidency']);
        } else if (response.role === 'SECRETARY') {
          this.router.navigate(['/secretariat']);
        } else {
          this.router.navigate(['/auth/login']);
        }
      })
    );
  }

  logout(): void {
    this.http.post('/auth/logout', {}).subscribe({
      next: () => {
        this.currentUser.set(null);
        this.router.navigate(['/auth/login']);
      },
      error: () => {
        // Even if the backend fails, clear local state and force redirect
        this.currentUser.set(null);
        this.router.navigate(['/auth/login']);
      }
    });
  }
}
