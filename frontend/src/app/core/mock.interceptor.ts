import { HttpInterceptorFn, HttpRequest, HttpResponse } from '@angular/common/http';
import { delay, of } from 'rxjs';
import { Store } from './models';

// Fake API for `ng serve`, active only in development builds. Delete a route's
// handler as soon as the real one exists: unmatched calls go to the backend.
const stores: Store[] = [
  { id: 1, name: 'Auchan', colour: '#e2001a', logo: null, selected: true },
  { id: 2, name: 'Carrefour', colour: '#004e9f', logo: null, selected: true },
  { id: 3, name: 'Lidl', colour: '#ffd500', logo: null, selected: false },
];

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
};

export const mockInterceptor: HttpInterceptorFn = (request, next) => {
  const handler = handlers[`${request.method} ${request.url}`];
  return handler
    ? of(new HttpResponse({ status: 200, body: handler(request) })).pipe(delay(300))
    : next(request);
};
