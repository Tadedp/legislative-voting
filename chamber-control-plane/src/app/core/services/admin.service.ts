import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private readonly http = inject(HttpClient);

  createLegislator(payload: { national_id: string; full_name: string }): Observable<any> {
    return this.http.post<any>('/legislators', payload);
  }

  regenerateProvisioningToken(legislatorId: string): Observable<any> {
    return this.http.post<any>(`/legislators/${legislatorId}/provisioning-token`, {});
  }

  getLegislators(): Observable<any[]> {
    return this.http.get<any[]>('/legislators');
  }

  wipeDevice(deviceId: string): Observable<any> {
    return this.http.post(`/devices/${deviceId}/wipe`, {});
  }
}
