import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Product, ReceiptResult, SearchResult } from '../core/models';
import { ro } from '../shared/ro';
import { Cart } from './cart';
import { CartService } from './cart.service';

const auchan: Product = {
  id: 5,
  store_id: 1,
  store_name: 'Auchan',
  name: 'Lapte 3.5% 1 l',
  brand: null,
  price: '8.50',
  image_url: null,
  updated_at: '2026-11-02T09:00:00Z',
};
const carrefour: Product = { ...auchan, id: 6, store_id: 2, store_name: 'Carrefour', name: 'Unt' };
const match: SearchResult[] = [{ size_category_id: 100, path: 'Lapte', generic: auchan }];
const receipt: ReceiptResult = {
  matched: [{ name: 'Lapte', line_total: '8.50' }],
  unmatched_items: [],
  estimate: '8.50',
  paid: '8.50',
  modifier: '1.00',
  points: 85,
};

describe('Cart', () => {
  let fixture: ComponentFixture<Cart>;
  let http: HttpTestingController;
  let page: HTMLElement;
  let cart: CartService;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Cart],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    cart = TestBed.inject(CartService);
  });

  afterEach(() => http.verify());

  async function open(): Promise<void> {
    fixture = TestBed.createComponent(Cart);
    page = fixture.nativeElement;
    await fixture.whenStable();
  }

  async function settle(): Promise<void> {
    await fixture.whenStable();
  }

  function button(selector: string): HTMLButtonElement {
    return page.querySelector<HTMLButtonElement>(selector)!;
  }

  function buttons(selector: string): HTMLButtonElement[] {
    return [...page.querySelectorAll<HTMLButtonElement>(selector)];
  }

  function type(input: HTMLInputElement, value: string): void {
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function rowTexts(): string[] {
    return buttons('.row').map((row) =>
      [...row.children].map((cell) => cell.textContent?.trim()).join(' '),
    );
  }

  async function addRow(name: string, quantity: string, price: string): Promise<void> {
    button('.add-row').click();
    await settle();
    type(page.querySelector<HTMLInputElement>('.new-name')!, name);
    type(page.querySelector<HTMLInputElement>('.new-quantity')!, quantity);
    type(page.querySelector<HTMLInputElement>('.new-price')!, price);
    page.querySelector('.new-row')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  function pickFile(selector: string, file: File): void {
    const input = page.querySelector<HTMLInputElement>(selector)!;
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
  }

  function fail(url: string | RegExp, status: number, detail?: string): void {
    http
      .expectOne((request) =>
        typeof url === 'string' ? request.url === url : url.test(request.url),
      )
      .flush({ detail }, { status, statusText: 'Error' });
  }

  describe('product list', () => {
    it('explains an empty cart', async () => {
      await open();

      expect(page.textContent).toContain(ro.cart.empty);
    });

    it('has product, quantity and price columns', async () => {
      await open();
      const heads = [...page.querySelectorAll('.head span')].map((cell) => cell.textContent);

      expect(heads).toEqual([ro.cart.product, ro.cart.quantity, ro.cart.price]);
    });

    it('shows each item in its own row', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '3.50' });
      await open();

      expect(rowTexts()).toEqual(['Mere 2 3,50 lei']);
    });

    it('opens a box for a new product when + is pressed', async () => {
      await open();
      expect(page.querySelector('.new-row')).toBeNull();

      button('.add-row').click();
      await settle();

      expect(page.querySelector('.new-name')).not.toBeNull();
    });

    it('adds the typed product and moves + below it', async () => {
      await open();

      await addRow('Mere', '2', '3,50');
      http.expectOne((r) => r.url === '/api/search').flush([]);
      await settle();

      expect(rowTexts()).toEqual(['Mere 2 3,50 lei']);
      expect(page.querySelector('.new-row')).toBeNull();
      const order = [...page.querySelector('.rows')!.children].map((el) => el.className);
      expect(order.at(-1)).toContain('add-row');
    });

    it('rejects bad details and sends nothing', async () => {
      await open();

      await addRow('', '0', 'abc');

      expect(page.textContent).toContain(ro.cart.invalidRow);
      expect(cart.items()).toEqual([]);
    });

    it('can cancel adding a product', async () => {
      await open();
      button('.add-row').click();
      await settle();

      button('.cancel-new').click();
      await settle();

      expect(page.querySelector('.new-row')).toBeNull();
    });

    it('finds which store sells a typed product', async () => {
      await open();

      await addRow('lapte', '1', '8');
      http.expectOne((r) => r.url === '/api/search').flush(match);
      await settle();

      expect(cart.stores()).toEqual([{ id: 1, name: 'Auchan' }]);
    });

    it('keeps a product when the store lookup fails', async () => {
      await open();

      await addRow('lapte', '1', '8');
      fail('/api/search', 500);
      await settle();

      expect(cart.items().length).toBe(1);
    });
  });

  describe('editing', () => {
    beforeEach(async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '3.50' });
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await open();
    });

    async function startEdit(): Promise<void> {
      button('.edit').click();
      await settle();
    }

    it('shows edit, not save, at first', () => {
      expect(button('.edit').textContent).toContain(ro.cart.edit);
      expect(page.querySelector('.save')).toBeNull();
      expect(page.querySelector('.remove')).toBeNull();
    });

    it('swaps edit for save and cancel, and shows a remove button per row', async () => {
      await startEdit();

      expect(page.querySelector('.edit')).toBeNull();
      expect(page.querySelector('.save')).not.toBeNull();
      expect(page.querySelector('.cancel')).not.toBeNull();
      expect(buttons('.remove').length).toBe(2);
    });

    it('hides + while editing', async () => {
      await startEdit();

      expect(page.querySelector('.add-row')).toBeNull();
    });

    it('edits the row that is picked', async () => {
      await startEdit();

      buttons('.row')[1].click();
      await settle();

      expect(page.querySelector<HTMLInputElement>('.edit-name')?.value).toBe('Pere');
    });

    it('saves the changes', async () => {
      await startEdit();
      buttons('.row')[0].click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.edit-quantity')!, '5');

      button('.save').click();
      await settle();

      expect(cart.items()[0].quantity).toBe('5');
      expect(page.querySelector('.edit')).not.toBeNull();
    });

    it('looks up the store again when a name changes', async () => {
      await startEdit();
      buttons('.row')[0].click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.edit-name')!, 'lapte');

      button('.save').click();
      http.expectOne((r) => r.url === '/api/search').flush(match);
      await settle();

      expect(cart.items()[0].storeName).toBe('Auchan');
    });

    it('cancel undoes every change', async () => {
      await startEdit();
      buttons('.remove')[0].click();
      await settle();
      buttons('.row')[0].click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.edit-quantity')!, '9');

      button('.cancel').click();
      await settle();

      expect(cart.items().map((item) => item.quantity)).toEqual(['2', '1']);
      expect(buttons('.row').length).toBe(2);
    });

    it('removes a row on save', async () => {
      await startEdit();

      buttons('.remove')[0].click();
      await settle();
      button('.save').click();
      await settle();

      expect(cart.items().map((item) => item.name)).toEqual(['Pere']);
    });

    it('refuses to save bad details', async () => {
      await startEdit();
      buttons('.row')[0].click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.edit-price')!, 'abc');

      button('.save').click();
      await settle();

      expect(page.textContent).toContain(ro.cart.invalidRow);
      expect(cart.items()[0].price).toBe('3.50');
      expect(page.querySelector('.save')).not.toBeNull();
    });
  });

  describe('import', () => {
    const pdf = new File(['%PDF'], 'lista.pdf', { type: 'application/pdf' });
    const photo = new File(['x'], 'lista.jpg', { type: 'image/jpeg' });

    it('hides the PDF and image choices at first', async () => {
      await open();

      expect(page.querySelector('.import-bar')?.classList.contains('open')).toBe(false);
    });

    it('opens the two choices when import is pressed, and closes them again', async () => {
      await open();

      button('.import').click();
      await settle();
      expect(page.querySelector('.import-bar')?.classList.contains('open')).toBe(true);
      expect(button('.import-pdf').textContent).toContain(ro.cart.pdf);
      expect(button('.import-image').textContent).toContain(ro.cart.image);

      button('.import').click();
      await settle();
      expect(page.querySelector('.import-bar')?.classList.contains('open')).toBe(false);
    });

    it('only accepts the right file types', async () => {
      await open();

      expect(page.querySelector('.pdf-input')?.getAttribute('accept')).toBe('application/pdf');
      expect(page.querySelector('.image-input')?.getAttribute('accept')).toBe('image/*');
    });

    it('fills the list from a PDF', async () => {
      await open();
      pickFile('.pdf-input', pdf);

      const request = http.expectOne('/api/imports');
      const body = request.request.body as FormData;
      expect(body.get('file')).toBe(pdf);
      expect(body.get('days')).toBe('1');
      request.flush({
        items: [{ food: 'lapte', size_category_id: 100, path: 'Lapte', packs: 2 }],
        unmapped: [],
      });
      http
        .expectOne('/api/categories/100/products')
        .flush({ generic: auchan, products: [auchan] });
      await settle();

      expect(cart.items()[0]).toMatchObject({
        name: 'Lapte 3.5% 1 l',
        quantity: '2',
        price: '8.50',
        storeName: 'Auchan',
      });
    });

    it('fills the list from an image', async () => {
      await open();
      pickFile('.image-input', photo);

      http.expectOne('/api/imports').flush({ items: [], unmapped: ['ghimbir'] });
      await settle();

      expect(cart.items()[0]).toMatchObject({ name: 'ghimbir', quantity: '1', price: '0' });
    });

    it('clears the price warning once editing starts', async () => {
      await open();
      pickFile('.image-input', photo);
      http.expectOne('/api/imports').flush({ items: [], unmapped: ['ghimbir'] });
      await settle();

      button('.edit').click();
      await settle();

      expect(page.textContent).not.toContain(ro.cart.needsPrice);
    });

    it('warns about foods it could not price', async () => {
      await open();
      pickFile('.image-input', photo);

      http.expectOne('/api/imports').flush({ items: [], unmapped: ['ghimbir'] });
      await settle();

      expect(page.textContent).toContain(ro.cart.needsPrice);
    });

    it('shows that it is reading, and blocks a second file', async () => {
      await open();
      button('.import').click();
      await settle();
      pickFile('.pdf-input', pdf);
      await settle();

      expect(button('.import').textContent).toContain(ro.cart.reading);
      expect(button('.import-pdf').disabled).toBe(true);
      http.expectOne('/api/imports').flush({ items: [], unmapped: [] });
    });

    it('asks for a retry when nothing could be read', async () => {
      await open();
      pickFile('.pdf-input', pdf);

      fail('/api/imports', 422);
      await settle();

      expect(page.textContent).toContain(ro.cart.importFailed);
    });

    it('explains a file that is too large', async () => {
      await open();
      pickFile('.pdf-input', pdf);

      fail('/api/imports', 413);
      await settle();

      expect(page.textContent).toContain(ro.cart.fileRejected);
    });
  });

  describe('summary', () => {
    it('shows the total for the quantities', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '3.50' });
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await open();

      expect(page.querySelector('.total')?.textContent).toContain('11,00 lei');
    });

    it('shows 100 points for every 10 lei', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await open();

      expect(page.querySelector('.earned')?.textContent).toContain('100');
    });

    it('updates after adding a product', async () => {
      await open();

      await addRow('Mere', '2', '5');
      http.expectOne((r) => r.url === '/api/search').flush([]);
      await settle();

      expect(page.querySelector('.total')?.textContent).toContain('10,00 lei');
    });

    it('explains when no store is known', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await open();

      expect(page.querySelector('.shops')?.textContent).toContain(ro.cart.noShops);
      expect(button('.directions').disabled).toBe(true);
      expect(button('.scan').disabled).toBe(true);
    });

    it('shows every store and picks the first', async () => {
      cart.addProduct(auchan);
      cart.addProduct(carrefour);
      await open();
      const shops = buttons('.shop');

      expect(shops.map((shop) => shop.textContent?.trim())).toEqual(['Auchan', 'Carrefour']);
      expect(shops[0].getAttribute('aria-pressed')).toBe('true');
    });

    it('lets the client pick another store', async () => {
      cart.addProduct(auchan);
      cart.addProduct(carrefour);
      await open();

      buttons('.shop')[1].click();
      await settle();

      expect(buttons('.shop')[1].getAttribute('aria-pressed')).toBe('true');
    });
  });

  describe('directions', () => {
    let opened: { location: { href: string }; close: () => void };

    function setLocation(result: 'allowed' | 'denied'): void {
      Object.defineProperty(navigator, 'geolocation', {
        configurable: true,
        value: {
          getCurrentPosition: (ok: PositionCallback, denied: PositionErrorCallback) =>
            result === 'allowed'
              ? ok({ coords: { latitude: 44.4, longitude: 26.1 } } as GeolocationPosition)
              : denied({ code: 1 } as GeolocationPositionError),
        },
      });
    }

    beforeEach(async () => {
      opened = { location: { href: '' }, close: vi.fn() };
      vi.spyOn(window, 'open').mockReturnValue(opened as unknown as Window);
      cart.addProduct(auchan);
      cart.addProduct(carrefour);
      await open();
    });

    afterEach(() => vi.restoreAllMocks());

    it('opens the maps link for the chosen store, using the location', async () => {
      setLocation('allowed');
      buttons('.shop')[1].click();
      await settle();

      button('.directions').click();
      const request = http.expectOne((r) => r.url === '/api/stores/2/directions');
      expect(request.request.params.get('lat')).toBe('44.4');
      expect(request.request.params.get('lng')).toBe('26.1');
      request.flush({ address: 'Strada 1', maps_url: 'https://maps.test/2' });

      expect(opened.location.href).toBe('https://maps.test/2');
    });

    it('still works when location is denied', () => {
      setLocation('denied');

      button('.directions').click();
      const request = http.expectOne((r) => r.url === '/api/stores/1/directions');
      expect(request.request.params.has('lat')).toBe(false);
      request.flush({ address: 'Strada 1', maps_url: 'https://maps.test/1' });

      expect(opened.location.href).toBe('https://maps.test/1');
    });

    it('explains a failure', async () => {
      setLocation('denied');

      button('.directions').click();
      fail(/directions$/, 500);
      await settle();

      expect(page.textContent).toContain(ro.cart.directionsFailed);
      expect(opened.close).toHaveBeenCalled();
    });
  });

  describe('receipt', () => {
    const photo = new File(['x'], 'bon.jpg', { type: 'image/jpeg' });

    beforeEach(async () => {
      cart.addProduct(auchan);
      await open();
    });

    function upload(): void {
      pickFile('.receipt-input', photo);
    }

    it('opens the camera, with a file picker as fallback', () => {
      const input = page.querySelector('.receipt-input');

      expect(input?.getAttribute('accept')).toBe('image/*');
      expect(input?.getAttribute('capture')).toBe('environment');
    });

    it('sends the photo for the chosen store and shows the points', async () => {
      upload();

      const request = http.expectOne((r) => /\/receipts$/.test(r.url));
      expect(request.request.params.get('store_id')).toBe('1');
      expect((request.request.body as FormData).get('file')).toBe(photo);
      request.flush(receipt);
      await settle();

      const result = page.querySelector('.receipt-result')?.textContent;
      expect(result).toContain(ro.cart.receiptValid);
      expect(result).toContain('85');
    });

    it('blocks a second upload while the first is running', async () => {
      upload();
      await settle();

      expect(button('.scan').disabled).toBe(true);
      http.expectOne((r) => /\/receipts$/.test(r.url)).flush(receipt);
    });

    it('explains a receipt that was already used', async () => {
      upload();

      fail(/\/receipts$/, 409);
      await settle();

      expect(page.textContent).toContain(ro.cart.receiptUsed);
    });

    it('shows the server reason for a wrong store', async () => {
      upload();

      fail(/\/receipts$/, 422, 'Bonul trebuie să fie de la Auchan');
      await settle();

      expect(page.textContent).toContain('Bonul trebuie să fie de la Auchan');
    });

    it('asks for a retake of an unreadable receipt', async () => {
      upload();

      fail(/\/receipts$/, 422);
      await settle();

      expect(page.textContent).toContain(ro.cart.receiptUnreadable);
    });

    it('can close the result', async () => {
      upload();
      http.expectOne((r) => /\/receipts$/.test(r.url)).flush(receipt);
      await settle();

      button('.close-result').click();
      await settle();

      expect(page.querySelector('.receipt-result')).toBeNull();
    });
  });
});
