import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiService } from '../core/api';
import { ImportPreview, SearchResult } from '../core/models';
import { ro } from '../shared/ro';

type ImportItem = ImportPreview['items'][number];

// The API sends these for a file it refuses. Anything else gets the general retry message.
const readErrors: Record<number, string> = {
  413: ro.import.tooLarge,
  415: ro.import.wrongType,
};

@Component({
  selector: 'app-import',
  styleUrl: './import.scss',
  templateUrl: './import.html',
})
export class Import {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly fileBox = viewChild<ElementRef<HTMLInputElement>>('fileBox');

  protected readonly ro = ro;
  protected readonly file = signal<File | null>(null);
  protected readonly text = signal('');
  protected readonly days = signal('7');
  protected readonly reading = signal(false);
  protected readonly readError = signal<string | null>(null);

  protected readonly reviewing = signal(false);
  protected readonly items = signal<ImportItem[]>([]);
  protected readonly unmapped = signal<string[]>([]);
  protected readonly listName = signal<string>(ro.import.defaultName);
  protected readonly saving = signal(false);
  protected readonly confirmFailed = signal(false);

  protected readonly picking = signal<string | null>(null);
  protected readonly pickQuery = signal('');
  protected readonly pickResults = signal<SearchResult[] | null>(null);
  protected readonly pickFailed = signal(false);

  protected readonly canRead = computed(
    () =>
      !this.reading() &&
      /^[1-9]\d*$/.test(this.days()) &&
      (this.file() !== null || this.text().trim() !== ''),
  );
  protected readonly canConfirm = computed(
    () =>
      !this.saving() &&
      this.items().length > 0 &&
      this.unmapped().length === 0 &&
      this.listName().trim() !== '',
  );

  // A list comes from one source, so choosing a file replaces any pasted text.
  protected chooseFile(input: HTMLInputElement): void {
    this.file.set(input.files?.[0] ?? null);
    this.text.set('');
  }

  protected typeText(value: string): void {
    this.text.set(value);
    this.file.set(null);
    const box = this.fileBox()?.nativeElement;
    if (box) {
      box.value = '';
    }
  }

  protected read(event: Event): void {
    event.preventDefault();
    if (!this.canRead()) {
      return;
    }
    const file = this.file();
    this.reading.set(true);
    this.readError.set(null);
    this.api
      .importList(Number(this.days()), file ? { file } : { text: this.text().trim() })
      .pipe(finalize(() => this.reading.set(false)))
      .subscribe({
        next: (preview) => {
          this.items.set(preview.items);
          this.unmapped.set(preview.unmapped);
          this.reviewing.set(true);
        },
        error: (error: HttpErrorResponse) =>
          this.readError.set(readErrors[error.status] ?? ro.import.failed),
      });
  }

  protected removeItem(index: number): void {
    this.items.update((items) => items.filter((_, position) => position !== index));
  }

  protected removeUnmapped(food: string): void {
    this.unmapped.update((foods) => foods.filter((item) => item !== food));
    if (this.picking() === food) {
      this.picking.set(null);
    }
  }

  protected startPicking(food: string): void {
    this.picking.set(food);
    this.pickQuery.set(food);
    this.pickResults.set(null);
    this.pickFailed.set(false);
  }

  protected searchPick(event: Event): void {
    event.preventDefault();
    const query = this.pickQuery().trim();
    if (!query) {
      return;
    }
    this.pickFailed.set(false);
    this.api.search(query).subscribe({
      next: (results) => this.pickResults.set(results),
      error: () => this.pickFailed.set(true),
    });
  }

  protected pick(food: string, result: SearchResult): void {
    const { size_category_id, path } = result;
    this.items.update((items) => [...items, { food, size_category_id, path, packs: 1 }]);
    this.removeUnmapped(food);
  }

  protected confirm(): void {
    if (!this.canConfirm()) {
      return;
    }
    this.saving.set(true);
    this.confirmFailed.set(false);
    const items = this.items().map(({ size_category_id, packs }) => ({ size_category_id, packs }));
    this.api
      .confirmImport({ name: this.listName().trim(), items })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: ({ list_id }) => void this.router.navigate(['/cart', `${list_id}`]),
        error: () => this.confirmFailed.set(true),
      });
  }

  protected startOver(): void {
    this.reviewing.set(false);
    this.file.set(null);
    this.text.set('');
    this.items.set([]);
    this.unmapped.set([]);
    this.picking.set(null);
    this.confirmFailed.set(false);
    this.listName.set(ro.import.defaultName);
  }
}
