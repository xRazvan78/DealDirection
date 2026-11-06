import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { filter, fromEvent, map } from 'rxjs';
import { ro } from './shared/ro';

const SCROLL_TOP_THRESHOLD = 200;

@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private readonly router = inject(Router);
  private readonly url = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.router.url),
    ),
    { initialValue: this.router.url },
  );

  protected readonly ro = ro;
  protected readonly showNavigation = computed(() => !this.url().startsWith('/login'));
  protected readonly menuOpen = signal(false);
  protected readonly tabs = [
    { path: '/browse', label: ro.nav.home, icon: 'home' },
    { path: '/cart', label: ro.nav.cart, icon: 'cart' },
    { path: '/cards', label: ro.nav.cards, icon: 'cards' },
  ];
  protected readonly menuLinks = [
    { path: '/lists', label: ro.nav.lists },
    { path: '/import', label: ro.nav.import },
    { path: '/wallet', label: ro.nav.wallet },
    { path: '/settings', label: ro.nav.settings },
  ];
  protected readonly showScrollTop = signal(false);
  private scroller: Element | null = null;

  constructor() {
    // Scroll events don't bubble, so capturing here covers every scrolling area.
    fromEvent(document, 'scroll', { capture: true, passive: true })
      .pipe(takeUntilDestroyed())
      .subscribe(({ target }) => {
        if (target instanceof Element) {
          this.scroller = target;
          this.showScrollTop.set(target.scrollTop > SCROLL_TOP_THRESHOLD);
        }
      });
    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.showScrollTop.set(false));
  }

  protected scrollToTop(): void {
    this.scroller?.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
