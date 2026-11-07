import { Injectable, computed, inject, signal } from '@angular/core';
import { CartItem, CartService } from '../cart/cart.service';
import { ApiService } from '../core/api';
import { ReceiptReading, StoredList } from '../core/models';
import { ro } from '../shared/ro';

export interface SavedList {
  id: number;
  name: string;
  items: CartItem[];
  updatedAt: string;
  // Set once the list has been bought. From then on it can only be viewed or deleted.
  receipt?: ReceiptReading;
  points?: number;
  // False until the backend has this version, so it can be sent again later.
  synced?: boolean;
}

const LISTS_KEY = 'dealdirection.lists';

// Lists are kept on this device so they open instantly and survive a lost connection, and
// the backend shares them with the client's other devices. They aren't the backend's
// shopping lists, whose items need a catalog category that typed products don't have.
// Editing happens in the cart: opening a list loads it there, and saving writes it back.
@Injectable({ providedIn: 'root' })
export class SavedListsService {
  private readonly api = inject(ApiService);
  private readonly cart = inject(CartService);

  readonly lists = signal<SavedList[]>(readSavedLists());
  readonly current = computed(
    // Another device can finish the open list. The cart then keeps it as an unsaved one.
    () =>
      this.lists().find((list) => list.id === this.cart.currentListId() && !list.receipt) ?? null,
  );
  readonly unsaved = computed(() => {
    const current = this.current();
    const items = this.cart.items();
    return current ? JSON.stringify(current.items) !== JSON.stringify(items) : items.length > 0;
  });

  nextDefaultName(): string {
    const taken = new Set(this.lists().map((list) => list.name));
    let number = 1;
    while (taken.has(`${ro.lists.defaultName} ${number}`)) {
      number++;
    }
    return `${ro.lists.defaultName} ${number}`;
  }

  // An open list keeps its name. A new one uses the given name, or the next default.
  saveCurrent(name = ''): void {
    const current = this.current();
    const updatedAt = new Date().toISOString();
    const items = this.cart.items();
    if (current) {
      const others = this.lists().filter((list) => list.id !== current.id);
      this.saveAndSend({ ...current, items, updatedAt }, others);
      return;
    }
    const list = { id: newId(), name: name.trim() || this.nextDefaultName(), items, updatedAt };
    this.saveAndSend(list, this.lists());
    this.cart.setCurrentList(list.id);
  }

  // Saves what's in the cart, then closes it with the receipt, which empties the cart.
  finish(receipt: ReceiptReading, points: number): void {
    this.saveCurrent();
    const saved = this.current();
    if (saved) {
      const others = this.lists().filter((list) => list.id !== saved.id);
      this.saveAndSend({ ...saved, receipt, points }, others);
    }
    this.cart.clear();
  }

  open(id: number): void {
    const list = this.lists().find((saved) => saved.id === id);
    if (list && !list.receipt) {
      this.cart.setCurrentList(id);
      this.cart.replace(list.items);
    }
  }

  startNew(): void {
    this.cart.clear();
  }

  rename(id: number, name: string): void {
    const trimmed = name.trim();
    if (trimmed) {
      const list = this.lists().find((saved) => saved.id === id);
      if (list && !list.receipt) {
        const renamed = { ...list, name: trimmed, updatedAt: new Date().toISOString() };
        this.saveAndSend(renamed, this.lists().filter((saved) => saved.id !== id));
      }
    }
  }

  remove(id: number): void {
    if (this.cart.currentListId() === id) {
      this.cart.setCurrentList(null);
    }
    this.save(this.lists().filter((list) => list.id !== id));
    // Without a connection the list comes back on the next sync, as nothing was lost.
    this.api.deleteSavedList(id).subscribe({ error: () => undefined });
  }

  // Takes in the other devices' changes, and sends what this one couldn't send before.
  // The backend decides what a list holds, except for changes it hasn't received yet.
  sync(): void {
    this.api.getSavedLists().subscribe({
      next: (stored) => {
        const waiting = this.lists().filter((list) => !list.synced);
        const ids = new Set(waiting.map((list) => list.id));
        const others = stored.filter((list) => !ids.has(list.id)).map(fromStored);
        this.save(
          [...waiting, ...others].sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt)),
        );
        waiting.forEach((list) => this.send(list));
      },
      error: () => undefined,
    });
  }

  clear(): void {
    this.lists.set([]);
    localStorage.removeItem(LISTS_KEY);
  }

  private saveAndSend(list: SavedList, others: SavedList[]): void {
    const changed = { ...list, synced: false };
    this.save([changed, ...others]);
    this.send(changed);
  }

  private send(list: SavedList): void {
    this.api.putSavedList(toStored(list)).subscribe({
      // Only if it wasn't changed again meanwhile. The answer can be a newer or finished version.
      next: (stored) =>
        this.save(this.lists().map((saved) => (saved === list ? fromStored(stored) : saved))),
      error: () => undefined,
    });
  }

  private save(lists: SavedList[]): void {
    this.lists.set(lists);
    localStorage.setItem(LISTS_KEY, JSON.stringify(lists));
  }
}

// Made on the device, so two devices saving at once can't pick the same id.
function newId(): number {
  return Date.now() * 1000 + Math.floor(Math.random() * 1000);
}

function toStored({ id, name, items, updatedAt, receipt, points }: SavedList): StoredList {
  return {
    id,
    name,
    items,
    updated_at: updatedAt,
    receipt: receipt ?? null,
    points: points ?? null,
  };
}

function fromStored(list: StoredList): SavedList {
  return {
    id: list.id,
    name: list.name,
    items: list.items as CartItem[],
    updatedAt: list.updated_at,
    ...(list.receipt ? { receipt: list.receipt, points: list.points ?? 0 } : {}),
    synced: true,
  };
}

function readSavedLists(): SavedList[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(LISTS_KEY) ?? '[]');
    return Array.isArray(saved) ? (saved as SavedList[]) : [];
  } catch {
    return [];
  }
}
