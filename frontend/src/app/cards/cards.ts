import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';
import { CardScan, LoyaltyCard } from '../core/models';
import { ro } from '../shared/ro';
import { CardsService } from './cards.service';

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

// Adding a card: photograph its code, then pick its supermarket, then save.
// The backend reads the code and redraws it cleanly for the till.
@Component({
  selector: 'app-cards',
  styleUrl: './cards.scss',
  templateUrl: './cards.html',
})
export class Cards implements OnInit {
  protected readonly wallet = inject(CardsService);

  protected readonly ro = ro;
  protected readonly choosing = signal(false);
  protected readonly scanning = signal(false);
  protected readonly saving = signal(false);
  // A code read from the photo, waiting for its brand.
  protected readonly scan = signal<CardScan | null>(null);
  // A photo with no readable code, which the client may save as it is.
  protected readonly unreadPhoto = signal<File | null>(null);
  protected readonly savingPhoto = signal(false);
  protected readonly photoPreview = signal<string | null>(null);
  protected readonly brand = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly viewing = signal<LoyaltyCard | null>(null);
  protected readonly confirmingDelete = signal(false);

  protected readonly pickingBrand = computed(() => this.scan() !== null || this.savingPhoto());

  ngOnInit(): void {
    this.wallet.load();
  }

  protected usePhoto(input: HTMLInputElement): void {
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    this.reset();
    if (!file.type.startsWith('image/') || file.size > MAX_PHOTO_BYTES) {
      this.error.set(ro.cards.wrongFile);
      return;
    }

    this.scanning.set(true);
    this.wallet
      .scan(file)
      .pipe(finalize(() => this.scanning.set(false)))
      .subscribe({
        next: (scan) => {
          this.choosing.set(false);
          this.scan.set(scan);
          const suggested = scan.suggested_brand;
          this.brand.set(suggested && !this.wallet.hasBrand(suggested) ? suggested : '');
        },
        error: (error: HttpErrorResponse) => {
          this.error.set(messageOf(error, ro.cards.noCode));
          // No code found: offer to keep the photo itself instead.
          if (error.status === 422) {
            this.unreadPhoto.set(file);
          }
        },
      });
  }

  protected savePhotoInstead(): void {
    const photo = this.unreadPhoto();
    if (!photo) {
      return;
    }
    this.choosing.set(false);
    this.error.set(null);
    this.savingPhoto.set(true);
    this.photoPreview.set(URL.createObjectURL(photo));
  }

  protected saveCard(event: Event): void {
    event.preventDefault();
    const brand = this.brand();
    if (!brand) {
      this.error.set(ro.cards.brandRequired);
      return;
    }
    const scan = this.scan();
    const photo = this.unreadPhoto();
    const source = scan ? { scan } : photo ? { photo } : null;
    if (!source) {
      return;
    }

    this.saving.set(true);
    this.error.set(null);
    this.wallet
      .add(brand, source)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: () => this.reset(),
        error: (error: HttpErrorResponse) => this.error.set(messageOf(error, ro.cards.saveFailed)),
      });
  }

  protected cancelCard(): void {
    this.reset();
  }

  protected deleteCard(card: LoyaltyCard): void {
    this.wallet.remove(card.id).subscribe({
      next: () => {
        this.confirmingDelete.set(false);
        this.viewing.set(null);
      },
      error: () => this.error.set(ro.cards.deleteFailed),
    });
  }

  private reset(): void {
    const preview = this.photoPreview();
    if (preview) {
      URL.revokeObjectURL(preview);
    }
    this.scan.set(null);
    this.unreadPhoto.set(null);
    this.savingPhoto.set(false);
    this.photoPreview.set(null);
    this.brand.set('');
    this.error.set(null);
  }
}

// The backend's Romanian message for a 4xx, or a fallback text.
function messageOf(error: HttpErrorResponse, fallback: string): string {
  const detail: unknown = (error.error as { detail?: unknown } | null)?.detail;
  return error.status >= 400 && error.status < 500 && typeof detail === 'string' ? detail : fallback;
}
