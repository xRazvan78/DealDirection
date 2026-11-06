import { HttpInterceptorFn, HttpRequest, HttpResponse } from '@angular/common/http';
import { delay, of } from 'rxjs';
import { Category, CategoryProducts, Product, Store } from './models';

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
  200: [mockProduct(4, 2, 'Pâine albă 500 g', '4.50')],
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

type Handler = (request: HttpRequest<unknown>) => unknown;

const handlers: Record<string, Handler> = {
  'POST /api/auth/register': () => ({ token: 'mock-token' }),
  'POST /api/auth/login': () => ({ token: 'mock-token' }),
  'POST /api/auth/demo': () => ({ token: 'mock-token' }),
  'GET /api/stores': () => stores,
  'PUT /api/me/stores': (request) => {
    const { store_ids } = request.body as { store_ids: number[] };
    stores.forEach((store) => (store.selected = store_ids.includes(store.id)));
    return null;
  },
  'GET /api/wallet': () => ({ balance: 1250, history: [] }),
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
    () => ({
      matched: [{ name: 'Lapte 3.5% 1 l', line_total: '8.50' }],
      unmatched_items: [],
      estimate: '8.50',
      paid: '8.50',
      modifier: '1.00',
      points: 85,
    }),
  ],
];

function idIn(url: string): number {
  return Number(url.match(/\d+/)?.[0]);
}

export const mockInterceptor: HttpInterceptorFn = (request, next) => {
  const handler =
    handlers[`${request.method} ${request.url}`] ??
    routesWithIds.find(
      ([route, method]) => method === request.method && route.test(request.url),
    )?.[2];
  return handler
    ? of(new HttpResponse({ status: 200, body: handler(request) })).pipe(delay(300))
    : next(request);
};
