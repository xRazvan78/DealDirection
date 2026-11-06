import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { ApiService } from '../core/api';
import { CardBrand, CardScan, LoyaltyCard } from '../core/models';

// The account's loyalty cards, kept on the backend so they follow the client
// to any phone. One card per brand: replacing a card means deleting it first.
@Injectable({ providedIn: 'root' })
export class CardsService {
  private readonly api = inject(ApiService);

  readonly cards = signal<LoyaltyCard[]>([]);
  readonly brands = signal<CardBrand[]>([]);

  load(): void {
    if (!this.brands().length) {
      this.api.getCardBrands().subscribe((brands) => this.brands.set(brands));
    }
    this.api.getCards().subscribe((cards) => this.cards.set(cards));
  }

  scan(photo: File): Observable<CardScan> {
    return this.api.scanCard(photo);
  }

  add(brand: string, source: { scan: CardScan } | { photo: File }): Observable<LoyaltyCard> {
    return this.api
      .saveCard(brand, source)
      .pipe(tap((card) => this.cards.update((cards) => [...cards, card])));
  }

  remove(id: number): Observable<void> {
    return this.api
      .deleteCard(id)
      .pipe(tap(() => this.cards.update((cards) => cards.filter((card) => card.id !== id))));
  }

  // On logout, so the next user doesn't see this account's cards.
  clear(): void {
    this.cards.set([]);
  }

  hasBrand(brand: string): boolean {
    return this.cards().some((card) => card.brand === brand);
  }
}
