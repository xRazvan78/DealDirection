import { DatePipe } from '@angular/common';
import {
  Component,
  DestroyRef,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Observable, Subscription } from 'rxjs';
import { CartService } from '../cart/cart.service';
import { ApiService } from '../core/api';
import { Category, CategoryProducts, Product, SearchResult } from '../core/models';
import { formatLei } from '../shared/format';
import { ro } from '../shared/ro';

@Component({
  imports: [DatePipe, RouterLink],
  selector: 'app-browse',
  styleUrl: './browse.scss',
  templateUrl: './browse.html',
})
export class Browse {
  private readonly api = inject(ApiService);
  private readonly cart = inject(CartService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly list = viewChild<ElementRef<HTMLElement>>('list');
  private request?: Subscription;

  protected readonly ro = ro;
  protected readonly formatLei = formatLei;
  protected readonly balance = signal<number | null>(null);
  protected readonly categories = signal<Category[]>([]);
  protected readonly trail = signal<Category[]>([]);
  protected readonly results = signal<SearchResult[] | null>(null);
  protected readonly products = signal<CategoryProducts | null>(null);
  protected readonly productsTitle = signal('');
  protected readonly query = signal('');
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  protected readonly addedId = signal<number | null>(null);
  protected readonly heading = computed(() => {
    if (this.products()) {
      return this.productsTitle();
    }
    return this.results() ? ro.browse.searchResults : (this.trail().at(-1)?.name ?? null);
  });

  constructor() {
    this.api
      .getWallet()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: ({ balance }) => this.balance.set(balance),
        error: () => this.balance.set(null),
      });
    this.load(this.api.getCategories(), (categories) => this.categories.set(categories));
  }

  protected open(category: Category): void {
    if (category.level === 'size') {
      this.openProducts(category.id, category.name);
      return;
    }
    this.load(this.api.getCategories(category.id), (categories) => {
      this.categories.set(categories);
      this.trail.update((trail) => [...trail, category]);
    });
  }

  protected openProducts(categoryId: number, title: string): void {
    this.load(this.api.getCategoryProducts(categoryId), (products) => {
      this.products.set(products);
      this.productsTitle.set(title);
    });
  }

  protected search(event: Event): void {
    event.preventDefault();
    const query = this.query().trim();
    if (!query) {
      return;
    }
    this.load(this.api.search(query), (results) => {
      this.products.set(null);
      this.results.set(results);
    });
  }

  protected addToCart(product: Product): void {
    this.cart.addProduct(product);
    this.addedId.set(product.id);
  }

  protected back(): void {
    this.scrollListToTop();
    if (this.products()) {
      this.products.set(null);
    } else if (this.results()) {
      this.results.set(null);
      this.query.set('');
    } else {
      const trail = this.trail().slice(0, -1);
      this.load(this.api.getCategories(trail.at(-1)?.id), (categories) => {
        this.categories.set(categories);
        this.trail.set(trail);
      });
    }
  }

  // Only the latest choice counts, so a new one cancels any request still running.
  private load<T>(source: Observable<T>, done: (value: T) => void): void {
    this.scrollListToTop();
    this.request?.unsubscribe();
    this.loading.set(true);
    this.failed.set(false);
    this.request = source.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (value) => {
        done(value);
        this.loading.set(false);
      },
      error: () => {
        this.failed.set(true);
        this.loading.set(false);
      },
    });
  }

  private scrollListToTop(): void {
    const list = this.list()?.nativeElement;
    if (list) {
      list.scrollTop = 0;
    }
  }
}
