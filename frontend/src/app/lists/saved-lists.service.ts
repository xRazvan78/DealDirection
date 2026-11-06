import { Injectable, computed, inject, signal } from '@angular/core';
import { CartItem, CartService } from '../cart/cart.service';
import { ro } from '../shared/ro';

export interface SavedList {
  id: number;
  name: string;
  items: CartItem[];
  updatedAt: string;
}

const LISTS_KEY = 'dealdirection.lists';

// Lists stay on this device, like the cart, because the backend's list items need a
// catalog category that typed products don't have. Editing happens in the cart: opening
// a list loads it there, and saving writes the cart back to that list.
@Injectable({ providedIn: 'root' })
export class SavedListsService {
  private readonly cart = inject(CartService);

  readonly lists = signal<SavedList[]>(readSavedLists());
  readonly current = computed(
    () => this.lists().find((list) => list.id === this.cart.currentListId()) ?? null,
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
      this.save([{ ...current, items, updatedAt }, ...others]);
      return;
    }
    const id = Math.max(0, ...this.lists().map((list) => list.id)) + 1;
    const list = { id, name: name.trim() || this.nextDefaultName(), items, updatedAt };
    this.save([list, ...this.lists()]);
    this.cart.setCurrentList(id);
  }

  open(id: number): void {
    const list = this.lists().find((saved) => saved.id === id);
    if (list) {
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
      this.save(this.lists().map((list) => (list.id === id ? { ...list, name: trimmed } : list)));
    }
  }

  remove(id: number): void {
    if (this.cart.currentListId() === id) {
      this.cart.setCurrentList(null);
    }
    this.save(this.lists().filter((list) => list.id !== id));
  }

  clear(): void {
    this.lists.set([]);
    localStorage.removeItem(LISTS_KEY);
  }

  private save(lists: SavedList[]): void {
    this.lists.set(lists);
    localStorage.setItem(LISTS_KEY, JSON.stringify(lists));
  }
}

function readSavedLists(): SavedList[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(LISTS_KEY) ?? '[]');
    return Array.isArray(saved) ? (saved as SavedList[]) : [];
  } catch {
    return [];
  }
}
