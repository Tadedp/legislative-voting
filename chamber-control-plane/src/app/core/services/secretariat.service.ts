import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface AgendaItem {
  id: string;
  category: 'PROJECT' | 'MOTION';
  file_number: string;
  title: string;
  summary: string;
  parliamentary_stage: 'INITIAL' | 'REVISION';
  status: string;
}

export type AgendaItemCreate = Omit<AgendaItem, 'id' | 'status' | 'parliamentary_stage'>;
export type AgendaItemUpdate = Partial<AgendaItemCreate> & { status?: string };

export interface SessionAttendanceEnriched {
  legislative_session_id: string;
  legislator_id: string;
  status: 'PRESENT' | 'ABSENT' | 'ON_LEAVE';
  full_name: string;
  national_id: string;
}

@Injectable({
  providedIn: 'root'
})
export class SecretariatService {
  private readonly http = inject(HttpClient);

  // Agenda Methods
  getAgendaItems(): Observable<AgendaItem[]> {
    return this.http.get<AgendaItem[]>('/agenda-items');
  }

  createAgendaItem(data: AgendaItemCreate): Observable<AgendaItem> {
    return this.http.post<AgendaItem>('/agenda-items', data);
  }

  updateAgendaItem(id: string, data: AgendaItemUpdate): Observable<AgendaItem> {
    return this.http.patch<AgendaItem>(`/agenda-items/${id}`, data);
  }

  deleteAgendaItem(id: string): Observable<AgendaItem> {
    return this.http.delete<AgendaItem>(`/agenda-items/${id}`);
  }

  // Attendance Methods
  getSessionAttendance(sessionId: string): Observable<SessionAttendanceEnriched[]> {
    return this.http.get<SessionAttendanceEnriched[]>(`/legislative-sessions/${sessionId}/attendance`);
  }

  updateAttendance(sessionId: string, legislatorId: string, status: 'PRESENT' | 'ABSENT' | 'ON_LEAVE'): Observable<any> {
    // Wrap the single record in a bulk array as per backend contract
    const payload = {
      records: [
        {
          legislator_id: legislatorId,
          status: status
        }
      ]
    };
    return this.http.post(`/legislative-sessions/${sessionId}/attendance/bulk`, payload);
  }
}
