import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { Observable, catchError, finalize, forkJoin, map, of, switchMap } from 'rxjs';
import { ApiService } from '../core/api';
import { ImportPreview, Product, ReceiptReading } from '../core/models';
import { formatLei, formatQuantity, formatReceiptDate } from '../shared/format';
import { isPrice, isQuantity, normalizeAmount } from '../shared/money';
import { ro } from '../shared/ro';
import { CartItem, CartService } from './cart.service';
import { CartPlan, comparePlans } from './plans';

// `/imports` scales a plan by days. A plain list has no days, so it stays as written.
const IMPORT_DAYS = 1;

interface PricedImport {
  item: ImportPreview['items'][number];
  generic: Product | null;
}

@Component({
  selector: 'app-cart',
  styleUrl: './cart.scss',
  templateUrl: './cart.html',
})
export class Cart {
  private readonly api = inject(ApiService);
  protected readonly cart = inject(CartService);

  protected readonly ro = ro;
  protected readonly formatLei = formatLei;
  protected readonly formatQuantity = formatQuantity;
  protected readonly formatReceiptDate = formatReceiptDate;

  protected readonly adding = signal(false);
  protected readonly newName = signal('');
  protected readonly newQuantity = signal('1');
  protected readonly newPrice = signal('');
  protected readonly addFailed = signal(false);

  protected readonly editing = signal(false);
  protected readonly draft = signal<CartItem[]>([]);
  protected readonly editingId = signal<number | null>(null);
  protected readonly editFailed = signal(false);
  protected readonly rows = computed(() => (this.editing() ? this.draft() : this.cart.items()));

  protected readonly importOpen = signal(false);
  protected readonly importing = signal(false);
  protected readonly importError = signal<string | null>(null);
  protected readonly importNote = signal<string | null>(null);

  private readonly chosenStoreId = signal<number | null>(null);
  protected readonly store = computed(() => {
    const stores = this.cart.stores();
    return stores.find(({ id }) => id === this.chosenStoreId()) ?? stores[0] ?? null;
  });

  private readonly categoryKey = computed(() => {
    const ids = this.cart.items().flatMap(({ sizeCategoryId }) => sizeCategoryId ?? []);
    return [...new Set(ids)].sort((a, b) => a - b).join(',');
  });
  private readonly offers = toSignal(
    toObservable(this.categoryKey).pipe(switchMap((key) => this.loadOffers(key))),
    { initialValue: new Map<number, Product[]>() },
  );
  protected readonly comparison = computed(() => comparePlans(this.cart.items(), this.offers()));

  protected readonly directionsFailed = signal(false);
  protected readonly scanning = signal(false);
  protected readonly receiptError = signal<string | null>(null);
  protected readonly receipt = signal<ReceiptReading | null>(null);

  protected isChosen(plan: CartPlan): boolean {
    const items = this.cart.items();
    return plan.lines.every(({ itemId, offer }) => {
      const item = items.find(({ id }) => id === itemId);
      return item?.storeId === offer.store_id && item.price === offer.price;
    });
  }

  protected choosePlan(plan: CartPlan): void {
    this.cart.applyPlan(plan.lines);
    this.chosenStoreId.set(null);
  }

  protected chooseStore(id: number): void {
    this.chosenStoreId.set(id);
  }

  protected startAdding(): void {
    this.newName.set('');
    this.newQuantity.set('1');
    this.newPrice.set('');
    this.addFailed.set(false);
    this.adding.set(true);
  }

  protected addRow(event: Event): void {
    event.preventDefault();
    const details = cleaned({
      name: this.newName(),
      quantity: this.newQuantity(),
      price: this.newPrice(),
    });
    if (!isValid(details)) {
      this.addFailed.set(true);
      return;
    }
    const item = this.cart.add(details);
    this.adding.set(false);
    this.findStore(item.id, item.name);
  }

  protected startEditing(): void {
    this.adding.set(false);
    this.draft.set(this.cart.items());
    this.editingId.set(null);
    this.editFailed.set(false);
    this.importNote.set(null);
    this.editing.set(true);
  }

  protected changeDraft(id: number, change: Partial<CartItem>): void {
    this.draft.update((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...change } : row)),
    );
  }

  protected removeRow(id: number): void {
    this.draft.update((rows) => rows.filter((row) => row.id !== id));
    if (this.editingId() === id) {
      this.editingId.set(null);
    }
  }

  protected saveEdits(): void {
    const rows = this.draft().map((row) => ({ ...row, ...cleaned(row) }));
    if (!rows.every(isValid)) {
      this.editFailed.set(true);
      return;
    }
    const previous = new Map(this.cart.items().map((item) => [item.id, item.name]));
    this.cart.replace(rows);
    this.editing.set(false);
    rows
      .filter((row) => row.name !== previous.get(row.id))
      .forEach((row) => this.findStore(row.id, row.name));
  }

  protected importFile(input: HTMLInputElement): void {
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    this.importing.set(true);
    this.importError.set(null);
    this.importNote.set(null);
    this.api
      .importList(IMPORT_DAYS, { file })
      .pipe(
        switchMap((preview) => this.priceImport(preview)),
        finalize(() => this.importing.set(false)),
      )
      .subscribe({
        next: ({ priced, unmapped }) => this.addImported(priced, unmapped),
        error: (error: HttpErrorResponse) =>
          this.importError.set(isFileRejected(error) ? ro.cart.fileRejected : ro.cart.importFailed),
      });
  }

  protected openDirections(): void {
    const store = this.store();
    if (!store) {
      return;
    }
    // Opened now, because browsers block pop-ups that aren't tied to the tap.
    const mapsWindow = window.open('', '_blank');
    this.directionsFailed.set(false);

    const open = (location?: { lat: number; lng: number }): void => {
      this.api.getDirections(store.id, location).subscribe({
        next: ({ maps_url }) => {
          if (mapsWindow) {
            mapsWindow.location.href = maps_url;
          } else {
            window.location.href = maps_url;
          }
        },
        error: () => {
          mapsWindow?.close();
          this.directionsFailed.set(true);
        },
      });
    };

    if (!navigator.geolocation) {
      open();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => open({ lat: coords.latitude, lng: coords.longitude }),
      () => open(),
      { timeout: 5000 },
    );
  }

  protected scanReceipt(input: HTMLInputElement): void {
    const photo = input.files?.[0];
    input.value = '';
    if (!photo) {
      return;
    }
    this.scanning.set(true);
    this.receiptError.set(null);
    this.receipt.set(null);
    this.api
      .readReceipt(photo)
      .pipe(finalize(() => this.scanning.set(false)))
      .subscribe({
        next: (reading) => this.receipt.set(reading),
        error: (error: HttpErrorResponse) => this.receiptError.set(receiptMessage(error)),
      });
  }

  private findStore(itemId: number, name: string): void {
    this.api.search(name).subscribe({
      next: (results) => {
        const match = results[0];
        const generic = match?.generic;
        if (generic) {
          this.cart.setStore(
            itemId,
            { id: generic.store_id, name: generic.store_name },
            match.size_category_id,
          );
        } else {
          this.cart.clearStore(itemId);
        }
      },
      // The product stays in the cart, just without a known store.
      error: () => undefined,
    });
  }

  // One price that fails to load only leaves that product out of the comparison.
  private loadOffers(key: string): Observable<Map<number, Product[]>> {
    if (!key) {
      return of(new Map<number, Product[]>());
    }
    const lookups = key.split(',').map((id) =>
      this.api.getCategoryProducts(Number(id)).pipe(
        map(({ products }): [number, Product[]] => [Number(id), products]),
        catchError(() => of<[number, Product[]]>([Number(id), []])),
      ),
    );
    return forkJoin(lookups).pipe(map((entries) => new Map(entries)));
  }

  private priceImport(preview: ImportPreview) {
    const lookups = preview.items.map((item) =>
      this.api
        .getCategoryProducts(item.size_category_id)
        .pipe(map(({ generic }): PricedImport => ({ item, generic }))),
    );
    return (lookups.length ? forkJoin(lookups) : of<PricedImport[]>([])).pipe(
      map((priced) => ({ priced, unmapped: preview.unmapped })),
    );
  }

  private addImported(priced: PricedImport[], unmapped: string[]): void {
    for (const { item, generic } of priced) {
      const quantity = String(item.packs);
      if (generic) {
        this.cart.add({
          name: generic.name,
          quantity,
          price: generic.price,
          store: { id: generic.store_id, name: generic.store_name },
          sizeCategoryId: item.size_category_id,
        });
      } else {
        this.cart.add({
          name: item.food,
          quantity,
          price: '0',
          sizeCategoryId: item.size_category_id,
        });
      }
    }
    unmapped.forEach((food) => this.cart.add({ name: food, quantity: '1', price: '0' }));
    if (unmapped.length || priced.some(({ generic }) => !generic)) {
      this.importNote.set(ro.cart.needsPrice);
    }
  }
}

function cleaned<T extends { name: string; quantity: string; price: string }>(details: T): T {
  return {
    ...details,
    name: details.name.trim(),
    quantity: normalizeAmount(details.quantity),
    price: normalizeAmount(details.price),
  };
}

function isValid({ name, quantity, price }: { name: string; quantity: string; price: string }) {
  return name !== '' && isQuantity(quantity) && isPrice(price);
}

function isFileRejected({ status }: HttpErrorResponse): boolean {
  return status === 413 || status === 415;
}

function receiptMessage(error: HttpErrorResponse): string {
  if (isFileRejected(error)) {
    return ro.cart.fileRejected;
  }
  if (error.status !== 422) {
    return ro.cart.receiptFailed;
  }
  const detail: unknown = (error.error as { detail?: unknown } | null)?.detail;
  return typeof detail === 'string' ? detail : ro.cart.receiptUnreadable;
}
