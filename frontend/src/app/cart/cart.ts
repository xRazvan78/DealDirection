import { HttpErrorResponse } from '@angular/common/http';
import {
  ApplicationRef,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { Observable, catchError, finalize, forkJoin, map, of, switchMap } from 'rxjs';
import { ApiService } from '../core/api';
import { Product, ReceiptReading, ShoppingRoute } from '../core/models';
import { SavedListsService } from '../lists/saved-lists.service';
import { ReceiptDialog } from '../receipt/receipt-dialog';
import { formatKm, formatLei } from '../shared/format';
import {
  addQuantities,
  decreaseQuantity,
  isPrice,
  isQuantity,
  normalizeAmount,
} from '../shared/money';
import { ro } from '../shared/ro';
import { CartItem, CartService } from './cart.service';
import { CartPlan, comparePlans } from './plans';

@Component({
  host: { '(window:resize)': 'keepFieldInView()' },
  imports: [ReceiptDialog],
  selector: 'app-cart',
  styleUrl: './cart.scss',
  templateUrl: './cart.html',
})
export class Cart {
  private readonly api = inject(ApiService);
  private readonly injector = inject(Injector);
  private readonly appRef = inject(ApplicationRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly newRow = viewChild<ElementRef<HTMLElement>>('newRow');
  protected readonly cart = inject(CartService);
  protected readonly lists = inject(SavedListsService);

  protected readonly ro = ro;
  protected readonly formatLei = formatLei;
  protected readonly formatKm = formatKm;

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

  protected readonly naming = signal(false);
  protected readonly listName = signal('');

  private readonly categoryKey = computed(() => {
    const ids = this.cart.items().flatMap(({ sizeCategoryId }) => sizeCategoryId ?? []);
    return [...new Set(ids)].sort((a, b) => a - b).join(',');
  });
  private readonly offers = toSignal(
    toObservable(this.categoryKey).pipe(switchMap((key) => this.loadOffers(key))),
    { initialValue: new Map<number, Product[]>() },
  );
  protected readonly comparison = computed(() => comparePlans(this.cart.items(), this.offers()));

  private readonly route = signal<ShoppingRoute | null>(null);
  // The route only counts while it covers exactly the cart's stores; otherwise Traseu comes back.
  protected readonly trip = computed(() => {
    const route = this.route();
    const cartIds = this.cart.stores().map(({ id }) => id).sort((a, b) => a - b);
    const routeIds = route?.stops.map(({ store_id }) => store_id).sort((a, b) => a - b);
    return route && routeIds?.join(',') === cartIds.join(',') ? route : null;
  });
  protected readonly routeError = signal<string | null>(null);
  protected readonly scanning = signal(false);
  protected readonly receiptError = signal<string | null>(null);
  protected readonly receipt = signal<ReceiptReading | null>(null);
  protected readonly accepting = signal(false);
  protected readonly acceptError = signal<string | null>(null);
  protected readonly earned = signal<number | null>(null);
  private receiptPhoto: File | null = null;

  // An open list already has a name, so only a new list asks for one.
  protected saveList(): void {
    if (this.lists.current()) {
      this.lists.saveCurrent();
      return;
    }
    this.listName.set('');
    this.naming.set(true);
  }

  protected confirmListName(event: Event): void {
    event.preventDefault();
    this.lists.saveCurrent(this.listName());
    this.naming.set(false);
  }

  protected isChosen(plan: CartPlan): boolean {
    const items = this.cart.items();
    return plan.lines.every(({ itemId, offer }) => {
      const item = items.find(({ id }) => id === itemId);
      return item?.storeId === offer.store_id && item.price === offer.price;
    });
  }

  protected choosePlan(plan: CartPlan): void {
    this.cart.applyPlan(plan.lines);
    this.route.set(null);
  }

  protected startAdding(): void {
    this.newName.set('');
    this.newQuantity.set('1');
    this.newPrice.set('');
    this.addFailed.set(false);
    this.adding.set(true);
    // Otherwise its buttons can sit below the visible part of the list.
    afterNextRender(
      () => this.newRow()?.nativeElement.scrollIntoView?.({ block: 'nearest' }),
      { injector: this.injector },
    );
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
    this.editing.set(true);
  }

  // Rendering now, inside the tap, is what lets a phone open its keyboard for this field.
  protected pickRow(id: number, event: Event): void {
    const cell = (event.target as HTMLElement).closest<HTMLElement>('[data-field]');
    this.editingId.set(id);
    this.appRef.tick();
    const input = this.host.nativeElement.querySelector<HTMLInputElement>(
      `.edit-${cell?.dataset['field'] ?? 'quantity'}`,
    );
    input?.focus();
    input?.select();
    this.keepFieldInView();
  }

  // A keyboard can shrink the page and cover the field being typed in.
  protected keepFieldInView(): void {
    const field = document.activeElement;
    if (field instanceof HTMLInputElement && this.host.nativeElement.contains(field)) {
      field.scrollIntoView?.({ block: 'center' });
    }
  }

  protected canDecrease(row: CartItem): boolean {
    return this.oneLess(row) !== null;
  }

  protected stepUp(row: CartItem, event: Event): void {
    event.stopPropagation();
    const quantity = normalizeAmount(row.quantity);
    this.changeDraft(row.id, {
      quantity: isQuantity(quantity) ? addQuantities(quantity, '1') : '1',
    });
  }

  protected stepDown(row: CartItem, event: Event): void {
    event.stopPropagation();
    const quantity = this.oneLess(row);
    if (quantity === null) {
      this.removeRow(row.id);
    } else {
      this.changeDraft(row.id, { quantity });
    }
  }

  // A row can hold a half-typed quantity, which has nothing to count down from.
  private oneLess(row: CartItem): string | null {
    const quantity = normalizeAmount(row.quantity);
    return isQuantity(quantity) ? decreaseQuantity(quantity) : null;
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

  // One Google Maps trip through every store in the cart, in the order the backend found shortest.
  // The app stays open and shows a link to tap: opening a tab before the route was
  // known left Android Chrome on a blank page, with the app paused behind it.
  protected openRoute(): void {
    const storeIds = this.cart.stores().map(({ id }) => id);
    if (!storeIds.length) {
      return;
    }
    this.routeError.set(null);
    this.route.set(null);

    const open = (location?: { lat: number; lng: number }): void => {
      this.api.getRoute(storeIds, location).subscribe({
        next: (route) => this.route.set(route),
        error: (error: HttpErrorResponse) => {
          this.routeError.set(
            error.status === 404 ? ro.cart.routeNoAddress : ro.cart.directionsFailed,
          );
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
    this.acceptError.set(null);
    this.earned.set(null);
    this.receiptPhoto = photo;
    this.api
      .readReceipt(photo)
      .pipe(finalize(() => this.scanning.set(false)))
      .subscribe({
        next: (reading) => this.receipt.set(reading),
        error: (error: HttpErrorResponse) => this.receiptError.set(receiptMessage(error)),
      });
  }

  // The list leaves the cart for good: from now on it's only in the saved lists.
  protected acceptReceipt(reading: ReceiptReading): void {
    if (!this.receiptPhoto) {
      return;
    }
    const name = this.lists.current()?.name ?? this.lists.nextDefaultName();
    const items = this.cart.items().map(({ name, quantity, price }) => ({ name, quantity, price }));
    this.accepting.set(true);
    this.acceptError.set(null);
    this.api
      .acceptReceipt(this.receiptPhoto, name, items)
      .pipe(finalize(() => this.accepting.set(false)))
      .subscribe({
        next: ({ points }) => this.closeList(reading, points),
        error: (error: HttpErrorResponse) => this.acceptError.set(receiptMessage(error)),
      });
  }

  protected closeReceipt(): void {
    this.receipt.set(null);
    this.earned.set(null);
  }

  private closeList(reading: ReceiptReading, points: number): void {
    this.lists.finish(reading, points);
    // The popup stays open, now showing what the receipt earned, until it's closed.
    this.earned.set(points);
    this.receiptPhoto = null;
    this.adding.set(false);
    this.editing.set(false);
    this.naming.set(false);
    this.route.set(null);
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
  if (error.status !== 422 && error.status !== 409) {
    return ro.cart.receiptFailed;
  }
  const detail: unknown = (error.error as { detail?: unknown } | null)?.detail;
  return typeof detail === 'string' ? detail : ro.cart.receiptUnreadable;
}
