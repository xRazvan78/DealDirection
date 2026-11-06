import { Injectable, computed, signal } from '@angular/core';
import { Product } from '../core/models';
import { addQuantities, pointsFor, totalOf } from '../shared/money';
import { PlanLine } from './plans';

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
  sizeCategoryId: number | null;
}

export interface NewCartItem {
  name: string;
  quantity: string;
  price: string;
  store?: StoreRef;
  sizeCategoryId?: number | null;
}

const CART_KEY = 'dealdirection.cart';

// Typed products have no catalog category, which the backend's list items
// require, so the cart stays on this device until the two are connected.
@Injectable({ providedIn: 'root' })
export class CartService {
  readonly items = signal<CartItem[]>(readSavedItems());
  readonly total = computed(() => totalOf(this.items()));
  readonly itemCount = computed(() =>
    this.items().reduce((count, item) => addQuantities(count, item.quantity), '0'),
  );
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

  add({ name, quantity, price, store, sizeCategoryId }: NewCartItem): CartItem {
    const item: CartItem = {
      id: Math.max(0, ...this.items().map((existing) => existing.id)) + 1,
      name,
      quantity,
      price,
      storeId: store?.id ?? null,
      storeName: store?.name ?? null,
      sizeCategoryId: sizeCategoryId ?? null,
    };
    this.replace([...this.items(), item]);
    return item;
  }

  addProduct(product: Product, sizeCategoryId?: number | null): void {
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
      sizeCategoryId,
    });
  }

  setStore(itemId: number, store: StoreRef, sizeCategoryId?: number): void {
    this.replace(
      this.items().map((item) =>
        item.id === itemId
          ? {
              ...item,
              storeId: store.id,
              storeName: store.name,
              sizeCategoryId: sizeCategoryId ?? item.sizeCategoryId,
            }
          : item,
      ),
    );
  }

  clearStore(itemId: number): void {
    this.replace(
      this.items().map((item) =>
        item.id === itemId
          ? { ...item, storeId: null, storeName: null, sizeCategoryId: null }
          : item,
      ),
    );
  }

  applyPlan(lines: PlanLine[]): void {
    this.replace(
      this.items().map((item) => {
        const offer = lines.find((line) => line.itemId === item.id)?.offer;
        return offer
          ? {
              ...item,
              price: offer.price,
              storeId: offer.store_id,
              storeName: offer.store_name,
            }
          : item;
      }),
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
