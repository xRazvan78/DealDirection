import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { filter, map } from 'rxjs';
import { ro } from './shared/ro';

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
  protected readonly tabs = [
    { path: '/browse', label: ro.nav.deals, icon: 'deals' },
    { path: '/cart', label: ro.nav.cart, icon: 'cart' },
    { path: '/cards', label: ro.nav.cards, icon: 'cards' },
  ];
}
