import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

// Add a screen by adding one route under the guarded parent. Paths match TEAM_TASKS.md.
export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./login/login').then((m) => m.Login) },
  {
    path: '',
    canActivateChild: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'browse' },
      { path: 'browse', loadComponent: () => import('./browse/browse').then((m) => m.Browse) },
      // `/cart` opens the current list, and CartService resolves its id in Task 15.
      { path: 'cart', loadComponent: () => import('./cart/cart').then((m) => m.Cart) },
      { path: 'cart/:listId', loadComponent: () => import('./cart/cart').then((m) => m.Cart) },
      { path: 'plan/:listId', loadComponent: () => import('./plan/plan').then((m) => m.Plan) },
      { path: 'import', loadComponent: () => import('./import/import').then((m) => m.Import) },
      { path: 'lists', loadComponent: () => import('./lists/lists').then((m) => m.Lists) },
      {
        path: 'receipt/:listId/:storeId',
        loadComponent: () => import('./receipt/receipt').then((m) => m.Receipt),
      },
      { path: 'wallet', loadComponent: () => import('./wallet/wallet').then((m) => m.Wallet) },
      { path: 'cards', loadComponent: () => import('./cards/cards').then((m) => m.Cards) },
      {
        path: 'settings',
        loadComponent: () => import('./settings/settings').then((m) => m.Settings),
      },
      { path: '**', redirectTo: 'browse' },
    ],
  },
];
