import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { CartService } from '../cart/cart.service';
import { formatLei } from '../shared/format';
import { totalOf } from '../shared/money';
import { ro } from '../shared/ro';
import { SavedList, SavedListsService } from './saved-lists.service';

// What to do once the cart's unsaved changes are dealt with: open a list, or start a new one.
type NextStep = { listId: number } | 'new';

@Component({
  imports: [DatePipe],
  selector: 'app-lists',
  styleUrl: './lists.scss',
  templateUrl: './lists.html',
})
export class Lists {
  private readonly router = inject(Router);
  protected readonly cart = inject(CartService);
  protected readonly saved = inject(SavedListsService);

  protected readonly ro = ro;
  protected readonly pending = signal<NextStep | null>(null);
  protected readonly renamingId = signal<number | null>(null);
  protected readonly newName = signal('');
  protected readonly deletingId = signal<number | null>(null);

  protected countOf(items: readonly unknown[]): string {
    return `${items.length} ${items.length === 1 ? ro.lists.product : ro.lists.products}`;
  }

  protected totalOf(list: SavedList): string {
    return formatLei(totalOf(list.items));
  }

  protected openCart(): void {
    void this.router.navigateByUrl('/cart');
  }

  protected openList(list: SavedList): void {
    if (list.id === this.saved.current()?.id) {
      this.openCart();
      return;
    }
    this.request({ listId: list.id });
  }

  protected startNew(): void {
    this.request('new');
  }

  protected saveFirst(): void {
    this.saved.saveCurrent();
    this.continue();
  }

  protected continue(): void {
    const step = this.pending();
    this.pending.set(null);
    if (step) {
      this.run(step);
    }
  }

  protected startRename(list: SavedList): void {
    this.deletingId.set(null);
    this.newName.set(list.name);
    this.renamingId.set(list.id);
  }

  protected saveName(event: Event, list: SavedList): void {
    event.preventDefault();
    this.saved.rename(list.id, this.newName());
    this.renamingId.set(null);
  }

  protected deleteList(list: SavedList): void {
    this.saved.remove(list.id);
    this.deletingId.set(null);
  }

  private request(step: NextStep): void {
    if (this.saved.unsaved()) {
      this.pending.set(step);
    } else {
      this.run(step);
    }
  }

  private run(step: NextStep): void {
    if (step === 'new') {
      this.saved.startNew();
    } else {
      this.saved.open(step.listId);
    }
    this.openCart();
  }
}
