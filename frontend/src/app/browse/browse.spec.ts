import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CartService } from '../cart/cart.service';
import { Category, CategoryProducts, Product, SearchResult, Wallet } from '../core/models';
import { ro } from '../shared/ro';
import { Browse } from './browse';

const wallet: Wallet = { balance: 1250, history: [] };
const topLevel: Category[] = [
  { id: 1, parent_id: null, name: 'Lapte', level: 'category' },
  { id: 2, parent_id: null, name: 'Pâine', level: 'category' },
];
const types: Category[] = [{ id: 10, parent_id: 1, name: '3.5%', level: 'type' }];
const sizes: Category[] = [{ id: 100, parent_id: 10, name: '1 l', level: 'size' }];
const product: Product = {
  id: 5,
  store_id: 1,
  store_name: 'Auchan',
  name: 'Lapte Zuzu 3.5% 1 l',
  brand: 'Zuzu',
  price: '8.5',
  image_url: null,
  updated_at: '2026-11-02T09:00:00Z',
};
const products: CategoryProducts = { generic: product, products: [product] };
const results: SearchResult[] = [
  { size_category_id: 100, path: 'Lapte > 3.5% > 1 l', generic: product },
];

describe('Browse', () => {
  let fixture: ComponentFixture<Browse>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Browse],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Browse);
    page = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  async function settle(): Promise<void> {
    await fixture.whenStable();
  }

  async function loadHome(): Promise<void> {
    http.expectOne('/api/wallet').flush(wallet);
    http.expectOne('/api/categories').flush(topLevel);
    await settle();
  }

  function rows(): HTMLButtonElement[] {
    return [...page.querySelectorAll<HTMLButtonElement>('.row')];
  }

  function expectCategories(parentId: number): ReturnType<HttpTestingController['expectOne']> {
    return http.expectOne((request) => {
      return request.url === '/api/categories' && request.params.get('parent_id') === `${parentId}`;
    });
  }

  async function openProducts(): Promise<void> {
    await loadHome();
    rows()[0].click();
    expectCategories(1).flush(types);
    await settle();
    rows()[0].click();
    expectCategories(10).flush(sizes);
    await settle();
    rows()[0].click();
    http.expectOne('/api/categories/100/products').flush(products);
    await settle();
  }

  async function search(query: string): Promise<void> {
    const input = page.querySelector<HTMLInputElement>('.search input')!;
    input.value = query;
    input.dispatchEvent(new Event('input'));
    page.querySelector('.search')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  it('shows a loading message, then the points balance', async () => {
    expect(page.textContent).toContain(ro.loading);

    await loadHome();

    expect(page.querySelector('.points')?.textContent).toContain('1250');
  });

  it('links the points box to the wallet', async () => {
    await loadHome();

    expect(page.querySelector('.points')?.getAttribute('href')).toBe('/wallet');
  });

  it('links Point Shop to the rewards', async () => {
    await loadHome();
    const shop = page.querySelector('.point-shop');

    expect(shop?.textContent).toContain(ro.browse.pointShop);
    expect(shop?.getAttribute('href')).toBe('/wallet#rewards');
  });

  it('keeps the page usable when the points fail to load', async () => {
    http.expectOne('/api/wallet').flush(null, { status: 500, statusText: 'Server Error' });
    http.expectOne('/api/categories').flush(topLevel);
    await settle();

    expect(page.querySelector('.points')?.textContent).toContain('–');
    expect(rows().length).toBe(2);
  });

  it('lists each category in its own box', async () => {
    await loadHome();

    expect(rows().map((row) => row.textContent?.trim())).toEqual(['Lapte', 'Pâine']);
  });

  it('shows no back button on the first level', async () => {
    await loadHome();

    expect(page.querySelector('.back')).toBeNull();
  });

  it('opens subcategories when a category is pressed', async () => {
    await loadHome();

    rows()[0].click();
    expectCategories(1).flush(types);
    await settle();

    expect(rows().map((row) => row.textContent?.trim())).toEqual(['3.5%']);
    expect(page.querySelector('.heading')?.textContent).toContain('Lapte');
  });

  it('goes back one level at a time', async () => {
    await loadHome();
    rows()[0].click();
    expectCategories(1).flush(types);
    await settle();

    page.querySelector<HTMLButtonElement>('.back')!.click();
    http.expectOne('/api/categories').flush(topLevel);
    await settle();

    expect(rows().map((row) => row.textContent?.trim())).toEqual(['Lapte', 'Pâine']);
    expect(page.querySelector('.back')).toBeNull();
  });

  it('shows products with price, store and update date at the size level', async () => {
    await openProducts();
    const text = page.querySelector('.products')?.textContent;

    expect(text).toContain('Lapte Zuzu 3.5% 1 l');
    expect(text).toContain('8,50 lei');
    expect(text).toContain('Auchan');
    expect(text).toContain('02.11.2026');
  });

  it('adds a product to the cart', async () => {
    await openProducts();

    page.querySelector<HTMLButtonElement>('.product .add')!.click();
    await settle();

    expect(TestBed.inject(CartService).items()[0]).toMatchObject({
      name: 'Lapte Zuzu 3.5% 1 l',
      storeName: 'Auchan',
    });
    expect(page.querySelector('.product .add')?.textContent).toContain(ro.browse.added);
  });

  it('adds the cheapest generic option to the cart', async () => {
    await openProducts();

    page.querySelector<HTMLButtonElement>('.generic .add')!.click();

    expect(TestBed.inject(CartService).items()[0].price).toBe('8.5');
  });

  it('highlights the cheapest generic option', async () => {
    await openProducts();

    expect(page.querySelector('.generic')?.textContent).toContain('8,50 lei');
  });

  it('returns to the sizes from the products without reloading', async () => {
    await openProducts();

    page.querySelector<HTMLButtonElement>('.back')!.click();
    await settle();

    expect(page.querySelector('.products')).toBeNull();
    expect(rows().map((row) => row.textContent?.trim())).toEqual(['1 l']);
  });

  it('searches when the form is submitted', async () => {
    await loadHome();

    await search('lapte');
    const request = http.expectOne((r) => r.url === '/api/search');
    expect(request.request.params.get('q')).toBe('lapte');
    request.flush(results);
    await settle();

    expect(rows()[0].textContent).toContain('Lapte > 3.5% > 1 l');
    expect(rows()[0].textContent).toContain('8,50 lei');
  });

  it('opens products from a search result', async () => {
    await loadHome();
    await search('lapte');
    http.expectOne((r) => r.url === '/api/search').flush(results);
    await settle();

    rows()[0].click();
    http.expectOne('/api/categories/100/products').flush(products);
    await settle();

    expect(page.querySelector('.products')?.textContent).toContain('Lapte Zuzu 3.5% 1 l');
  });

  it('explains when a search finds nothing', async () => {
    await loadHome();

    await search('xyz');
    http.expectOne((r) => r.url === '/api/search').flush([]);
    await settle();

    expect(page.textContent).toContain(ro.browse.noResults);
  });

  it('returns to the categories after leaving a search', async () => {
    await loadHome();
    await search('lapte');
    http.expectOne((r) => r.url === '/api/search').flush(results);
    await settle();

    page.querySelector<HTMLButtonElement>('.back')!.click();
    await settle();

    expect(rows().map((row) => row.textContent?.trim())).toEqual(['Lapte', 'Pâine']);
    expect(page.querySelector<HTMLInputElement>('.search input')?.value).toBe('');
  });

  it('does not search for an empty box', async () => {
    await loadHome();

    await search('   ');

    http.expectNone((r) => r.url === '/api/search');
  });

  it('shows a message when categories fail to load', async () => {
    http.expectOne('/api/wallet').flush(wallet);
    http.expectOne('/api/categories').flush(null, { status: 500, statusText: 'Server Error' });
    await settle();

    expect(page.textContent).toContain(ro.browse.loadFailed);
  });

  it('ignores an older reply when a newer choice was made', async () => {
    await loadHome();
    rows()[0].click();
    const older = expectCategories(1);
    await settle();

    await search('lapte');
    http.expectOne((r) => r.url === '/api/search').flush(results);
    await settle();

    expect(older.cancelled).toBe(true);
  });

  it('always shows the seasonal offers box', async () => {
    await loadHome();

    expect(page.querySelector('.seasonal')?.textContent).toContain(ro.browse.seasonalTitle);
  });

  it('starts each new view at the top of the list', async () => {
    await loadHome();
    const list = page.querySelector<HTMLElement>('.list')!;
    list.scrollTop = 300;

    rows()[0].click();

    expect(list.scrollTop).toBe(0);
    expectCategories(1).flush(types);
  });

  it('returns to the top when leaving the products', async () => {
    await openProducts();
    const list = page.querySelector<HTMLElement>('.list')!;
    list.scrollTop = 300;

    page.querySelector<HTMLButtonElement>('.back')!.click();

    expect(list.scrollTop).toBe(0);
  });

  it('links the seasonal offers box to the deals page', async () => {
    await loadHome();

    expect(page.querySelector('.seasonal')?.getAttribute('href')).toBe('/deals');
  });
});
