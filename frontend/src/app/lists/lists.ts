import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api';
import { ShoppingList } from '../core/models';
import { ro } from '../shared/ro';

@Component({
  imports: [RouterLink],
  selector: 'app-lists',
  styleUrl: './lists.scss',
  templateUrl: './lists.html',
})
export class Lists {
  private readonly api = inject(ApiService);

  protected readonly ro = ro;
  protected readonly lists = signal<ShoppingList[] | null>(null);
  protected readonly loadFailed = signal(false);
  protected readonly saveFailed = signal(false);
  protected readonly renamingId = signal<number | null>(null);
  protected readonly newName = signal('');

  constructor() {
    this.api.getLists().subscribe({
      next: (lists) => this.lists.set(lists),
      error: () => this.loadFailed.set(true),
    });
  }

  protected linkTo(list: ShoppingList): string[] {
    return [list.state === 'draft' ? '/cart' : '/plan', `${list.id}`];
  }

  protected startRename(list: ShoppingList): void {
    this.saveFailed.set(false);
    this.newName.set(list.name);
    this.renamingId.set(list.id);
  }

  protected cancelRename(): void {
    this.renamingId.set(null);
  }

  protected saveName(event: Event, list: ShoppingList): void {
    event.preventDefault();
    const name = this.newName().trim();
    if (!name) {
      return;
    }
    this.saveFailed.set(false);
    this.api.renameList(list.id, name).subscribe({
      next: (renamed) => {
        this.lists.update((lists) =>
          (lists ?? []).map((item) => (item.id === list.id ? { ...item, ...renamed } : item)),
        );
        this.renamingId.set(null);
      },
      error: () => this.saveFailed.set(true),
    });
  }

  protected remove(list: ShoppingList): void {
    if (!window.confirm(ro.lists.confirmDelete)) {
      return;
    }
    this.saveFailed.set(false);
    this.api.deleteList(list.id).subscribe({
      next: () => this.lists.update((lists) => (lists ?? []).filter((item) => item.id !== list.id)),
      error: () => this.saveFailed.set(true),
    });
  }
}
