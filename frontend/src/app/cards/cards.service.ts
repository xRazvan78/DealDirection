import { Injectable, signal } from '@angular/core';

export interface SavedCard {
  id: number;
  label: string;
  image: string;
}

const CARDS_KEY = 'dealdirection.cards';

// `/cards` expects a store id and clients here type a free label, so cards stay
// on this device until the backend accepts labels.
@Injectable({ providedIn: 'root' })
export class CardsService {
  readonly cards = signal<SavedCard[]>(readSavedCards());

  // False means the device has no room left, and nothing was saved.
  add(label: string, image: string): boolean {
    const id = Math.max(0, ...this.cards().map((card) => card.id)) + 1;
    return this.save([...this.cards(), { id, label, image }]);
  }

  remove(id: number): void {
    this.save(this.cards().filter((card) => card.id !== id));
  }

  clear(): void {
    this.cards.set([]);
    localStorage.removeItem(CARDS_KEY);
  }

  private save(cards: SavedCard[]): boolean {
    try {
      localStorage.setItem(CARDS_KEY, JSON.stringify(cards));
    } catch {
      return false;
    }
    this.cards.set(cards);
    return true;
  }
}

function readSavedCards(): SavedCard[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(CARDS_KEY) ?? '[]');
    return Array.isArray(saved) ? (saved as SavedCard[]) : [];
  } catch {
    return [];
  }
}
