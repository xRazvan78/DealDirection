import { Component, inject, signal } from '@angular/core';
import { ro } from '../shared/ro';
import { CardImageReader } from './card-image';
import { CardsService, SavedCard } from './cards.service';

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

@Component({
  selector: 'app-cards',
  styleUrl: './cards.scss',
  templateUrl: './cards.html',
})
export class Cards {
  private readonly reader = inject(CardImageReader);
  protected readonly wallet = inject(CardsService);

  protected readonly ro = ro;
  protected readonly choosing = signal(false);
  protected readonly reading = signal(false);
  protected readonly newImage = signal<string | null>(null);
  protected readonly newLabel = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly viewing = signal<SavedCard | null>(null);
  protected readonly confirmingDelete = signal(false);

  protected async usePhoto(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    this.error.set(null);
    if (!file.type.startsWith('image/') || file.size > MAX_PHOTO_BYTES) {
      this.error.set(ro.cards.wrongFile);
      return;
    }

    this.reading.set(true);
    try {
      this.newImage.set(await this.reader.read(file));
      this.newLabel.set('');
      this.choosing.set(false);
    } catch {
      this.error.set(ro.cards.readFailed);
    } finally {
      this.reading.set(false);
    }
  }

  protected saveCard(event: Event): void {
    event.preventDefault();
    const label = this.newLabel().trim();
    const image = this.newImage();
    if (!label || !image) {
      this.error.set(ro.cards.labelRequired);
      return;
    }
    if (!this.wallet.add(label, image)) {
      this.error.set(ro.cards.noRoom);
      return;
    }
    this.cancelCard();
  }

  protected cancelCard(): void {
    this.newImage.set(null);
    this.error.set(null);
  }

  protected deleteCard(card: SavedCard): void {
    this.wallet.remove(card.id);
    this.confirmingDelete.set(false);
    this.viewing.set(null);
  }
}
