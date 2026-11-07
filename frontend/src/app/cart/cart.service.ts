import { Injectable, computed, signal } from '@angular/core';
import { Product } from '../core/models';
import { addQuantities, decreaseQuantity, pointsFor, totalOf } from '../shared/money';
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
  productId: number | null;
}

export interface NewCartItem {
  name: string;
  quantity: string;
  price: string;
  store?: StoreRef;
  sizeCategoryId?: number | null;
  productId?: number;
}

const CART_KEY = 'dealdirection.cart';
const CURRENT_LIST_KEY = 'dealdirection.currentList';

// Typed products have no catalog category, which the backend's list items
// require, so the cart stays on this device until the two are connected.
@Injectable({ providedIn: 'root' })
export class CartService {
  readonly items = signal<CartItem[]>(readSavedItems());
  // The saved list open in the cart, or null for a list that isn't saved yet.
  readonly currentListId = signal<number | null>(readCurrentListId());
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

  add({ name, quantity, price, store, sizeCategoryId, productId }: NewCartItem): CartItem {
    const item: CartItem = {
      id: Math.max(0, ...this.items().map((existing) => existing.id)) + 1,
      name,
      quantity,
      price,
      storeId: store?.id ?? null,
      storeName: store?.name ?? null,
      sizeCategoryId: sizeCategoryId ?? null,
      productId: productId ?? null,
    };
    this.replace([...this.items(), item]);
    return item;
  }

  addProduct(product: Product, sizeCategoryId?: number | null): void {
    const existing = this.itemFor(product);
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
      productId: product.id,
    });
  }

  quantityOf(product: Product): string | null {
    return this.itemFor(product)?.quantity ?? null;
  }

  decreaseProduct(product: Product): void {
    const existing = this.itemFor(product);
    if (existing) {
      this.decreaseItem(existing.id);
    }
  }

  // Removes the item when one less would leave nothing.
  decreaseItem(itemId: number): void {
    this.replace(
      this.items().flatMap((item) => {
        if (item.id !== itemId) {
          return [item];
        }
        const quantity = decreaseQuantity(item.quantity);
        return quantity === null ? [] : [{ ...item, quantity }];
      }),
    );
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
              productId: offer.id,
            }
          : item;
      }),
    );
  }

  // Items saved before products had an id are matched by name and store.
  private itemFor(product: Product): CartItem | undefined {
    return this.items().find((item) =>
      item.productId
        ? item.productId === product.id
        : item.name === product.name && item.storeId === product.store_id,
    );
  }

  replace(items: CartItem[]): void {
    this.items.set(items);
    localStorage.setItem(CART_KEY, JSON.stringify(items));
  }

  setCurrentList(id: number | null): void {
    this.currentListId.set(id);
    if (id === null) {
      localStorage.removeItem(CURRENT_LIST_KEY);
    } else {
      localStorage.setItem(CURRENT_LIST_KEY, String(id));
    }
  }

  clear(): void {
    this.items.set([]);
    localStorage.removeItem(CART_KEY);
    this.setCurrentList(null);
  }
}

function readCurrentListId(): number | null {
  const id = Number(localStorage.getItem(CURRENT_LIST_KEY));
  return Number.isInteger(id) && id > 0 ? id : null;
}

function readSavedItems(): CartItem[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(CART_KEY) ?? '[]');
    return Array.isArray(saved) ? (saved as CartItem[]) : [];
  } catch {
    return [];
  }
}
