import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService } from '../core/api';
import { AuthService } from '../core/auth';
import { Store } from '../core/models';
import { LANGUAGES, Language, language, setLanguage } from '../shared/language';
import { ro } from '../shared/ro';

@Component({
  selector: 'app-settings',
  styleUrl: './settings.scss',
  templateUrl: './settings.html',
})
export class Settings {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly ro = ro;
  protected readonly languages = LANGUAGES;
  protected readonly language = language;
  protected readonly stores = signal<Store[] | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.api.getStores().subscribe({
      next: (stores) => this.stores.set(stores),
      error: () => this.error.set(ro.settings.loadFailed),
    });
  }

  protected toggle(store: Store, input: HTMLInputElement): void {
    const previous = this.stores() ?? [];
    const updated = previous.map((item) =>
      item.id === store.id ? { ...item, selected: input.checked } : item,
    );
    this.stores.set(updated);
    this.saving.set(true);
    this.error.set(null);

    const selectedIds = updated.filter((item) => item.selected).map((item) => item.id);
    this.api
      .setMyStores(selectedIds)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        error: () => {
          this.stores.set(previous);
          input.checked = store.selected;
          this.error.set(ro.settings.saveFailed);
        },
      });
  }

  protected choose(code: Language): void {
    setLanguage(code);
  }

  protected logout(): void {
    this.auth.logout();
    void this.router.navigateByUrl('/login');
  }
}
