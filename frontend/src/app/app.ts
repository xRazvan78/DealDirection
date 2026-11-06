import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ro } from './shared/ro';

@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  protected readonly ro = ro;
  protected readonly tabs = [
    { path: '/browse', label: ro.nav.browse },
    { path: '/cart', label: ro.nav.cart },
    { path: '/lists', label: ro.nav.lists },
    { path: '/wallet', label: ro.nav.wallet },
    { path: '/cards', label: ro.nav.cards },
  ];
}
