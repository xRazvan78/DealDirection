import {
  HttpErrorResponse,
  HttpEvent,
  HttpInterceptorFn,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http';
import { Observable, catchError, delay, of, throwError } from 'rxjs';
import { Category, CategoryProducts, Product, Reward, Store, Voucher, Wallet } from './models';

// Fake API for `ng serve`, active only in development builds. Delete a route's
// handler as soon as the real one exists: unmatched calls go to the backend.
const stores: Store[] = [
  { id: 1, name: 'Auchan', colour: '#e2001a', logo: null, selected: true },
  { id: 2, name: 'Carrefour', colour: '#004e9f', logo: null, selected: true },
  { id: 3, name: 'Lidl', colour: '#ffd500', logo: null, selected: false },
];

const categories: Category[] = [
  { id: 1, parent_id: null, name: 'Lapte', level: 'category' },
  { id: 2, parent_id: null, name: 'Pâine', level: 'category' },
  { id: 3, parent_id: null, name: 'Ouă', level: 'category' },
  { id: 4, parent_id: null, name: 'Brânzeturi', level: 'category' },
  { id: 5, parent_id: null, name: 'Fructe', level: 'category' },
  { id: 6, parent_id: null, name: 'Legume', level: 'category' },
  { id: 7, parent_id: null, name: 'Carne', level: 'category' },
  { id: 8, parent_id: null, name: 'Băuturi', level: 'category' },
  { id: 9, parent_id: null, name: 'Cafea și ceai', level: 'category' },
  { id: 12, parent_id: null, name: 'Conserve', level: 'category' },
  { id: 13, parent_id: null, name: 'Dulciuri', level: 'category' },
  { id: 14, parent_id: null, name: 'Făină și zahăr', level: 'category' },
  { id: 15, parent_id: null, name: 'Gustări', level: 'category' },
  { id: 16, parent_id: null, name: 'Iaurt', level: 'category' },
  { id: 17, parent_id: null, name: 'Mezeluri', level: 'category' },
  { id: 18, parent_id: null, name: 'Orez și paste', level: 'category' },
  { id: 19, parent_id: null, name: 'Ulei și oțet', level: 'category' },
  { id: 21, parent_id: null, name: 'Unt și margarină', level: 'category' },
  { id: 22, parent_id: null, name: 'Produse congelate', level: 'category' },
  { id: 23, parent_id: null, name: 'Curățenie', level: 'category' },
  { id: 10, parent_id: 1, name: '3.5%', level: 'type' },
  { id: 11, parent_id: 1, name: 'Ovăz', level: 'type' },
  { id: 20, parent_id: 2, name: 'Albă', level: 'type' },
  { id: 100, parent_id: 10, name: '1 l', level: 'size' },
  { id: 110, parent_id: 11, name: '1 l', level: 'size' },
  { id: 200, parent_id: 20, name: '500 g', level: 'size' },
  { id: 40, parent_id: 4, name: 'Telemea', level: 'type' },
  { id: 400, parent_id: 40, name: '500 g', level: 'size' },
  { id: 70, parent_id: 7, name: 'Pui', level: 'type' },
  { id: 700, parent_id: 70, name: '1 kg', level: 'size' },
];

function mockProduct(id: number, storeId: number, name: string, price: string): Product {
  return {
    id,
    store_id: storeId,
    store_name: stores.find((store) => store.id === storeId)?.name ?? '',
    name,
    brand: null,
    price,
    image_url: null,
    updated_at: '2026-11-02T09:00:00Z',
  };
}

const productsBySize: Record<number, Product[]> = {
  100: [mockProduct(1, 1, 'Lapte 3.5% 1 l', '8.50'), mockProduct(2, 2, 'Lapte 3.5% 1 l', '8.90')],
  110: [mockProduct(3, 1, 'Lapte de ovăz 1 l', '12.90')],
  200: [mockProduct(4, 2, 'Pâine albă 500 g', '4.50'), mockProduct(5, 1, 'Pâine albă 500 g', '5.20')],
  400: [mockProduct(6, 1, 'Telemea 500 g', '17.90'), mockProduct(7, 2, 'Telemea 500 g', '28.90')],
  700: [mockProduct(8, 2, 'Piept de pui 1 kg', '23.90'), mockProduct(9, 1, 'Piept de pui 1 kg', '34.90')],
};

function productsFor(sizeId: number): CategoryProducts {
  const products = productsBySize[sizeId] ?? [];
  return { generic: products[0] ?? null, products };
}

function pathOf(sizeId: number): string {
  const names: string[] = [];
  let current = categories.find((category) => category.id === sizeId);
  while (current) {
    names.unshift(current.name);
    current = categories.find((category) => category.id === current?.parent_id);
  }
  return names.join(' > ');
}

// Kept in memory, so a page reload resets the points.
const wallet: Wallet = {
  balance: 1250,
  history: [{ amount: 1250, reason: 'Puncte de test', created_at: '2026-11-02T09:00:00Z' }],
};

const rewards: Reward[] = [
  { id: 1, name: 'Cafea gratuită', cost: 500, store_name: 'Auchan' },
  { id: 2, name: 'Reducere de 10 lei', cost: 1000, store_name: 'Carrefour' },
  { id: 3, name: 'Reducere de 50 lei', cost: 5000, store_name: 'Auchan' },
];

const vouchers: Voucher[] = [];

function createVoucher(reward: Reward): Voucher {
  const expires = new Date();
  expires.setDate(expires.getDate() + 30);
  return {
    id: vouchers.length + 1,
    code: `DEMO-${String(100000 + vouchers.length * 7919)}`,
    reward_name: reward.name,
    store_name: reward.store_name,
    expires_at: expires.toISOString(),
  };
}

function recordPoints(amount: number, reason: string): void {
  wallet.balance += amount;
  wallet.history.unshift({ amount, reason, created_at: new Date().toISOString() });
}

type Handler = (request: HttpRequest<unknown>) => unknown;

const handlers: Record<string, Handler> = {
  'GET /api/stores': () => stores,
  // Visits the stores in the order asked, at made-up Sibiu addresses.
  'GET /api/stores/route': (request) => {
    const ids = (request.params.getAll('store_ids') ?? []).map(Number);
    const stops = ids.map((id, index) => ({
      store_id: id,
      store_name: stores.find((store) => store.id === id)?.name ?? '',
      address: `Adresă de test ${index + 1}, Sibiu`,
      lat: 45.79 + index / 100,
      lng: 24.15,
      km: request.params.has('lat') || index > 0 ? 1.1 : null,
    }));
    const destination = stops.at(-1);
    return {
      stops,
      total_km: stops.reduce((sum, { km }) => sum + (km ?? 0), 0),
      maps_url: `https://www.google.com/maps/dir/?api=1&destination=${destination?.lat},${destination?.lng}`,
    };
  },
  'PUT /api/me/stores': (request) => {
    const { store_ids } = request.body as { store_ids: number[] };
    stores.forEach((store) => (store.selected = store_ids.includes(store.id)));
    return null;
  },
  'GET /api/wallet': () => ({ ...wallet, history: [...wallet.history] }),
  'GET /api/rewards': () => rewards,
  'GET /api/vouchers': () => [...vouchers],
  'GET /api/categories': (request) => {
    const parentId = request.params.get('parent_id');
    return categories.filter(
      (category) => category.parent_id === (parentId === null ? null : Number(parentId)),
    );
  },
  'GET /api/search': (request) => {
    const query = (request.params.get('q') ?? '').toLowerCase();
    return Object.keys(productsBySize)
      .map(Number)
      .filter((sizeId) => pathOf(sizeId).toLowerCase().includes(query))
      .map((sizeId) => ({
        size_category_id: sizeId,
        path: pathOf(sizeId),
        generic: productsFor(sizeId).generic,
      }));
  },
  'POST /api/imports': () => ({
    items: [
      { food: 'lapte', size_category_id: 100, path: pathOf(100), packs: 2 },
      { food: 'paine', size_category_id: 200, path: pathOf(200), packs: 1 },
    ],
    unmapped: ['ghimbir'],
  }),
};

const routesWithIds: [RegExp, string, Handler][] = [
  [/^\/api\/categories\/\d+\/products$/, 'GET', ({ url }) => productsFor(idIn(url))],
  [
    /^\/api\/stores\/\d+\/directions$/,
    'GET',
    () => ({
      address: 'Adresă de test',
      maps_url: 'https://www.google.com/maps/dir/?api=1&destination=44.4268,26.1025',
    }),
  ],
  [
    /^\/api\/lists\/\d+\/receipts$/,
    'POST',
    () => {
      recordPoints(85, 'Bon validat');
      return {
        matched: [{ name: 'Lapte 3.5% 1 l', line_total: '8.50' }],
        unmatched_items: [],
        estimate: '8.50',
        paid: '8.50',
        modifier: '1.00',
        points: 85,
      };
    },
  ],
  [
    /^\/api\/rewards\/\d+\/redeem$/,
    'POST',
    ({ url }) => {
      const reward = rewards.find(({ id }) => id === idIn(url));
      if (!reward) {
        return null;
      }
      recordPoints(-reward.cost, reward.name);
      const voucher = createVoucher(reward);
      vouchers.unshift(voucher);
      return voucher;
    },
  ],
];

function idIn(url: string): number {
  return Number(url.match(/\d+/)?.[0]);
}

// With the backend off, login still works during development. A real rejection,
// like a wrong password, stays an error.
function withDemoLogin(response: Observable<HttpEvent<unknown>>): Observable<HttpEvent<unknown>> {
  return response.pipe(
    catchError((error: HttpErrorResponse) =>
      error.status === 0 || error.status >= 500
        ? of(new HttpResponse({ status: 200, body: { token: 'mock-token' } }))
        : throwError(() => error),
    ),
  );
}

export const mockInterceptor: HttpInterceptorFn = (request, next) => {
  if (request.url.startsWith('/api/auth/')) {
    return withDemoLogin(next(request));
  }
  const handler =
    handlers[`${request.method} ${request.url}`] ??
    routesWithIds.find(
      ([route, method]) => method === request.method && route.test(request.url),
    )?.[2];
  return handler
    ? of(new HttpResponse({ status: 200, body: handler(request) })).pipe(delay(300))
    : next(request);
};
