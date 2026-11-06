import { Injectable, signal } from '@angular/core';

// Task 14: keep the token in localStorage, and add login, demo login and logout.
@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly token = signal<string | null>(null);
}
