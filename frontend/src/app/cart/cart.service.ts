import { Injectable, computed, signal } from '@angular/core';
import { Product } from '../core/models';
import { addQuantities, pointsFor, totalOf } from '../shared/money';

export interface StoreRef {
  id: number;
  name: string;
}

export interface CartItem {
  id: number;
  name: string;
  quantity: string;
  price: string;
  storeId: number | null;
  storeName: string | null;
}

export interface NewCartItem {
  name: string;
  quantity: string;
  price: string;
  store?: StoreRef;
}

const CART_KEY = 'dealdirection.cart';

// Typed products have no catalog category, which the backend's list items
// require, so the cart stays on this device until the two are connected.
@Injectable({ providedIn: 'root' })
export class CartService {
  readonly items = signal<CartItem[]>(readSavedItems());
  readonly total = computed(() => totalOf(this.items()));
  readonly points = computed(() => pointsFor(this.total()));
  readonly stores = computed(() => {
    const stores = new Map<number, string>();
    for (const { storeId, storeName } of this.items()) {
      if (storeId !== null && storeName !== null) {
        stores.set(storeId, storeName);
      }
    }
    return [...stores].map(([id, name]): StoreRef => ({ id, name }));
  });

  add({ name, quantity, price, store }: NewCartItem): CartItem {
    const item: CartItem = {
      id: Math.max(0, ...this.items().map((existing) => existing.id)) + 1,
      name,
      quantity,
      price,
      storeId: store?.id ?? null,
      storeName: store?.name ?? null,
    };
    this.replace([...this.items(), item]);
    return item;
  }

  addProduct(product: Product): void {
    const existing = this.items().find(
      (item) => item.name === product.name && item.storeId === product.store_id,
    );
    if (existing) {
      this.replace(
        this.items().map((item) =>
          item === existing
            ? { ...item, quantity: addQuantities(item.quantity, '1') }
            : item,
        ),
      );
      return;
    }
    this.add({
      name: product.name,
      quantity: '1',
      price: product.price,
      store: { id: product.store_id, name: product.store_name },
    });
  }

  setStore(itemId: number, store: StoreRef): void {
    this.replace(
      this.items().map((item) =>
        item.id === itemId ? { ...item, storeId: store.id, storeName: store.name } : item,
      ),
    );
  }

  replace(items: CartItem[]): void {
    this.items.set(items);
    localStorage.setItem(CART_KEY, JSON.stringify(items));
  }

  clear(): void {
    this.items.set([]);
    localStorage.removeItem(CART_KEY);
  }
}

function readSavedItems(): CartItem[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(CART_KEY) ?? '[]');
    return Array.isArray(saved) ? (saved as CartItem[]) : [];
  } catch {
    return [];
  }
}
