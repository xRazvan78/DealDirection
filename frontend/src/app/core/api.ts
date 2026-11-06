import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

// One typed method per backend route. Screens call this service, never HttpClient.
// Money arrives as strings: format it with formatLei and never use parseFloat.
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>('/api/health');
  }
}
