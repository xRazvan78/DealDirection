import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { CardsService } from '../cards/cards.service';
import { CartService } from '../cart/cart.service';
import { ApiService } from './api';
import { AuthResponse, Credentials } from './models';

const TOKEN_KEY = 'dealdirection.token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly cart = inject(CartService);
  private readonly cards = inject(CardsService);

  readonly token = signal<string | null>(localStorage.getItem(TOKEN_KEY));

  login(details: Credentials): Observable<AuthResponse> {
    return this.api.login(details).pipe(tap(({ token }) => this.save(token)));
  }

  register(details: Credentials): Observable<AuthResponse> {
    return this.api.register(details).pipe(tap(({ token }) => this.save(token)));
  }

  demo(): Observable<AuthResponse> {
    return this.api.demo().pipe(tap(({ token }) => this.save(token)));
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    this.token.set(null);
    this.cart.clear();
    this.cards.clear();
  }

  private save(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
    this.token.set(token);
  }
}
