import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Product, ReceiptReading, SearchResult, ShoppingRoute } from '../core/models';
import { SavedListsService } from '../lists/saved-lists.service';
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
const receipt: ReceiptReading = {
  store_name: 'Lidl',
  purchased_at: '2026-10-26T11:39:00',
  identifier: 'Z 0347 / BF 0025',
  identifier_printed: true,
  total: '21.84',
  deposits: '0',
  lines: [
    { name: 'Chips preparate manual', quantity: '2.000', line_total: '15.98' },
    { name: 'Banane', quantity: '0.734', line_total: '5.86' },
  ],
};
const unreadFields: ReceiptReading = {
  store_name: null,
  purchased_at: null,
  identifier: null,
  identifier_printed: false,
  total: null,
  deposits: '0',
  lines: receipt.lines,
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

  afterEach(() => {
    answerOffers(() => []);
    http.verify();
  });

  function answerOffers(offersFor: (categoryId: number) => Product[]): void {
    http
      .match((request) => /\/api\/categories\/\d+\/products$/.test(request.url))
      .filter((request) => !request.cancelled)
      .forEach((request) => {
        const categoryId = Number(request.request.url.match(/\d+/)?.[0]);
        request.flush({ generic: null, products: offersFor(categoryId) });
      });
  }

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

  async function pickFirstRow(): Promise<void> {
    buttons('.row')[0].click();
    await settle();
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

    it('scrolls the new box fully into view', async () => {
      const scrollIntoView = vi.fn();
      Element.prototype.scrollIntoView = scrollIntoView;
      await open();

      button('.add-row').click();
      await settle();

      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' });
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
      expect(cart.items()[0].sizeCategoryId).toBe(100);
    });

    it('keeps a product when the store lookup fails', async () => {
      await open();

      await addRow('lapte', '1', '8');
      fail('/api/search', 500);
      await settle();

      expect(cart.items().length).toBe(1);
    });
  });

  describe('quantity buttons', () => {
    async function startEdit(): Promise<void> {
      await open();
      button('.edit').click();
      await settle();
    }

    async function press(selector: string, row = 0): Promise<void> {
      page.querySelectorAll('.row')[row].querySelector<HTMLButtonElement>(selector)!.click();
      await settle();
    }

    async function save(): Promise<void> {
      button('.save').click();
      await settle();
    }

    function hasButton(selector: string): boolean {
      return page.querySelector(`.row ${selector}`) !== null;
    }

    it('shows only the number outside edit mode', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await open();

      expect(hasButton('.increase')).toBe(false);
      expect(hasButton('.decrease')).toBe(false);
      expect(hasButton('.trash')).toBe(false);
      expect(rowTexts()).toEqual(['Mere 2 5,00 lei']);
    });

    it('shows no trash bin outside edit mode, even at quantity 1', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await open();

      expect(hasButton('.trash')).toBe(false);
    });

    it('puts a minus and a plus on either side of the number in edit mode', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await startEdit();
      const counter = page.querySelector('.row .quantity')!;

      expect([...counter.children].map((child) => child.classList[0])).toEqual([
        'decrease',
        'count',
        'increase',
      ]);
      expect(counter.querySelector('.count')?.textContent?.trim()).toBe('2');
    });

    it('applies a raised quantity on save', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await startEdit();

      await press('.increase');
      expect(page.querySelector('.row .count')?.textContent?.trim()).toBe('3');
      expect(cart.items()[0].quantity).toBe('2');

      await save();
      expect(cart.items()[0].quantity).toBe('3');
      expect(page.querySelector('.total')?.textContent).toContain('15,00 lei');
    });

    it('applies a lowered quantity on save', async () => {
      cart.add({ name: 'Mere', quantity: '3', price: '5' });
      await startEdit();

      await press('.decrease');
      await save();

      expect(cart.items()[0].quantity).toBe('2');
    });

    it('undoes quantity changes on cancel', async () => {
      cart.add({ name: 'Mere', quantity: '3', price: '5' });
      await startEdit();

      await press('.increase');
      await press('.increase');
      button('.cancel').click();
      await settle();

      expect(cart.items()[0].quantity).toBe('3');
      expect(rowTexts()).toEqual(['Mere 3 5,00 lei']);
    });

    it('shows a trash bin instead of a minus at quantity 1', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await startEdit();

      expect(hasButton('.trash')).toBe(true);
      expect(hasButton('.decrease')).toBe(false);
      expect(page.querySelector('.row .trash')?.getAttribute('aria-label')).toBe(
        `${ro.cart.remove} Mere`,
      );
    });

    it('changes the minus to a trash bin on the way down to 1', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await startEdit();

      await press('.decrease');

      expect(hasButton('.trash')).toBe(true);
    });

    it('changes the trash bin back to a minus on the way up', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await startEdit();

      await press('.increase');

      expect(hasButton('.decrease')).toBe(true);
      expect(hasButton('.trash')).toBe(false);
    });

    it('removes only that product with the trash bin, on save', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await startEdit();

      await press('.trash', 0);
      expect(cart.items().length).toBe(2);

      await save();
      expect(cart.items().map((item) => item.name)).toEqual(['Pere']);
    });

    it('brings a trashed product back on cancel', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await startEdit();

      await press('.trash');
      button('.cancel').click();
      await settle();

      expect(cart.items().length).toBe(1);
      expect(rowTexts()).toEqual(['Mere 1 5,00 lei']);
    });

    it('shows the trash bin for a weighed amount under 1', async () => {
      cart.add({ name: 'Mere', quantity: '0.5', price: '5' });
      await startEdit();

      expect(hasButton('.trash')).toBe(true);
    });

    it('steps a weighed amount by one', async () => {
      cart.add({ name: 'Mere', quantity: '1.5', price: '5' });
      await startEdit();

      await press('.decrease');
      await save();

      expect(cart.items()[0].quantity).toBe('0.5');
    });

    it('does not open the row when the plus or minus is pressed', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      await startEdit();

      await press('.increase');

      expect(page.querySelector('.edit-quantity')).toBeNull();
    });

    it('survives an unfinished quantity left in another row', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await startEdit();
      await press('[data-field="quantity"]', 0);
      type(page.querySelector<HTMLInputElement>('.edit-quantity')!, 'abc');

      await press('[data-field="name"]', 1);
      await press('.increase', 0);

      expect(page.querySelector('.row .count')?.textContent?.trim()).toBe('1');
    });

    it('accepts a comma quantity left in another row', async () => {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await startEdit();
      await press('[data-field="quantity"]', 0);
      type(page.querySelector<HTMLInputElement>('.edit-quantity')!, '2,5');

      await press('[data-field="name"]', 1);
      await press('.increase', 0);

      expect(page.querySelector('.row .count')?.textContent?.trim()).toBe('3.5');
    });

    it('counts as an unsaved change on a saved list', async () => {
      const lists = TestBed.inject(SavedListsService);
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
      lists.saveCurrent('Săptămâna');
      await startEdit();

      await press('.increase');
      await save();

      expect(lists.unsaved()).toBe(true);
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

    it('swaps edit for save and cancel, and shows a counter per row', async () => {
      await startEdit();

      expect(page.querySelector('.edit')).toBeNull();
      expect(page.querySelector('.save')).not.toBeNull();
      expect(page.querySelector('.cancel')).not.toBeNull();
      expect(buttons('.increase').length).toBe(2);
      expect(buttons('.remove').length).toBe(0);
    });

    it('offers delete on the opened row, for any quantity', async () => {
      await startEdit();

      await pickFirstRow();

      expect(buttons('.remove').length).toBe(1);
    });

    it('hides + while editing', async () => {
      await startEdit();

      expect(page.querySelector('.add-row')).toBeNull();
    });

    function tapCell(field: string): void {
      buttons('.row')[0].querySelector<HTMLElement>(`[data-field="${field}"]`)!.click();
    }

    function focused(): HTMLInputElement {
      return document.activeElement as HTMLInputElement;
    }

    it('goes straight to the quantity when it is tapped', async () => {
      await startEdit();

      tapCell('quantity');
      await settle();

      expect(focused().classList.contains('edit-quantity')).toBe(true);
    });

    it('goes straight to the price when it is tapped', async () => {
      await startEdit();

      tapCell('price');
      await settle();

      expect(focused().classList.contains('edit-price')).toBe(true);
    });

    it('goes straight to the name when it is tapped', async () => {
      await startEdit();

      tapCell('name');
      await settle();

      expect(focused().classList.contains('edit-name')).toBe(true);
    });

    it('selects the value, so typing replaces it', async () => {
      await startEdit();

      tapCell('quantity');
      await settle();

      expect(focused().selectionStart).toBe(0);
      expect(focused().selectionEnd).toBe(1);
    });

    it('types a new quantity after one tap, and saves it', async () => {
      await startEdit();

      tapCell('quantity');
      await settle();
      type(focused(), '7');
      button('.save').click();
      await settle();

      expect(cart.items()[0].quantity).toBe('7');
    });

    it('keeps the field in view when the keyboard opens', async () => {
      const scrollIntoView = vi.fn();
      Element.prototype.scrollIntoView = scrollIntoView;
      await startEdit();
      tapCell('quantity');
      await settle();
      scrollIntoView.mockClear();

      window.dispatchEvent(new Event('resize'));

      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' });
    });

    it('leaves the page alone on a resize with nothing being typed', async () => {
      const scrollIntoView = vi.fn();
      Element.prototype.scrollIntoView = scrollIntoView;
      await startEdit();

      window.dispatchEvent(new Event('resize'));

      expect(scrollIntoView).not.toHaveBeenCalled();
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
      await pickFirstRow();
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

      await pickFirstRow();
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

  describe('saving the list', () => {
    function addSomething(): void {
      cart.add({ name: 'Mere', quantity: '2', price: '5' });
    }

    function lists(): SavedListsService {
      return TestBed.inject(SavedListsService);
    }

    async function saveWithName(name: string): Promise<void> {
      button('.save-list').click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.list-name-input')!, name);
      page.querySelector('.name-form')!.dispatchEvent(new Event('submit'));
      await settle();
    }

    it('cannot save an empty cart', async () => {
      await open();

      expect(button('.save-list').disabled).toBe(true);
    });

    it('asks for a name, suggesting the default', async () => {
      addSomething();
      await open();

      button('.save-list').click();
      await settle();

      const input = page.querySelector<HTMLInputElement>('.list-name-input');
      expect(input?.value).toBe('');
      expect(input?.placeholder).toBe('Lista 1');
    });

    it('saves under the typed name and shows it', async () => {
      addSomething();
      await open();

      await saveWithName('Săptămâna');

      expect(lists().lists()[0].name).toBe('Săptămâna');
      expect(page.querySelector('.list-title')?.textContent).toContain('Săptămâna');
      expect(page.querySelector('.name-form')).toBeNull();
    });

    it('uses Lista 1 when no name is typed', async () => {
      addSomething();
      await open();

      await saveWithName('');

      expect(lists().lists()[0].name).toBe('Lista 1');
    });

    it('can cancel naming', async () => {
      addSomething();
      await open();
      button('.save-list').click();
      await settle();

      button('.cancel-name').click();
      await settle();

      expect(page.querySelector('.name-form')).toBeNull();
      expect(lists().lists()).toEqual([]);
    });

    it('shows Salvat with nothing new to save', async () => {
      addSomething();
      await open();

      await saveWithName('Săptămâna');

      expect(button('.save-list').disabled).toBe(true);
      expect(button('.save-list').textContent).toContain(ro.cart.saved);
    });

    it('saves an open list straight away, without asking again', async () => {
      addSomething();
      await open();
      await saveWithName('Săptămâna');
      cart.add({ name: 'Pere', quantity: '1', price: '4' });
      await settle();
      answerOffers(() => []);

      button('.save-list').click();
      await settle();

      expect(page.querySelector('.name-form')).toBeNull();
      expect(lists().lists()[0].items.length).toBe(2);
    });

    it('lets edits to an opened list work like any cart', async () => {
      addSomething();
      await open();
      await saveWithName('Săptămâna');

      button('.edit').click();
      await settle();
      await pickFirstRow();
      buttons('.remove')[0].click();
      await settle();
      button('.save').click();
      await settle();

      expect(cart.items()).toEqual([]);
      expect(button('.save-list').disabled).toBe(false);
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
    });

    it('lists every store in the cart', async () => {
      cart.addProduct(auchan);
      cart.addProduct(carrefour);
      await open();

      expect(page.querySelectorAll('button.shop').length).toBe(0);
      expect([...page.querySelectorAll('.shop')].map((shop) => shop.textContent?.trim())).toEqual([
        'Auchan',
        'Carrefour',
      ]);
    });
  });

  describe('store comparison', () => {
    const lapteAuchan: Product = { ...auchan, id: 11, price: '20' };
    const lapteCarrefour: Product = { ...carrefour, id: 12, name: 'Lapte', price: '10' };
    const untAuchan: Product = { ...auchan, id: 13, name: 'Unt', price: '10' };
    const untCarrefour: Product = { ...carrefour, id: 14, price: '20' };

    function offersFor(categoryId: number): Product[] {
      return categoryId === 100 ? [lapteAuchan, lapteCarrefour] : [untAuchan, untCarrefour];
    }

    async function openWithTwoItems(): Promise<void> {
      cart.add({ name: 'Lapte', quantity: '1', price: '20', sizeCategoryId: 100 });
      cart.add({ name: 'Unt', quantity: '1', price: '10', sizeCategoryId: 200 });
      await open();
    }

    it('compares nothing when no product is in the catalog', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await open();

      expect(page.querySelector('.plans')).toBeNull();
    });

    it('shows the best single store and the cheaper split', async () => {
      await openWithTwoItems();

      answerOffers(offersFor);
      await settle();

      const single = button('.plan-single').textContent;
      expect(single).toContain(ro.cart.singlePlan);
      expect(single).toContain('30,00 lei');
      expect(single).toContain('Auchan');
      const split = button('.plan-split').textContent;
      expect(split).toContain(ro.cart.splitPlan);
      expect(split).toContain('20,00 lei');
      expect(split).toContain('10,00 lei');
    });

    it('explains when splitting is not worth it', async () => {
      await openWithTwoItems();

      answerOffers(() => [lapteAuchan]);
      await settle();

      expect(page.querySelector('.plan-split')).toBeNull();
      expect(page.textContent).toContain(ro.cart.splitNotWorth);
    });

    it('moves each product to its cheapest store when the split is chosen', async () => {
      await openWithTwoItems();
      answerOffers(offersFor);
      await settle();

      button('.plan-split').click();
      await settle();

      expect(cart.items().map((item) => [item.storeName, item.price])).toEqual([
        ['Carrefour', '10'],
        ['Auchan', '10'],
      ]);
      expect(page.querySelector('.total')?.textContent).toContain('20,00 lei');
      expect(button('.plan-split').getAttribute('aria-pressed')).toBe('true');
      expect(button('.plan-single').getAttribute('aria-pressed')).toBe('false');
    });

    it('moves everything to one store when the single store is chosen', async () => {
      await openWithTwoItems();
      answerOffers(offersFor);
      await settle();

      button('.plan-single').click();
      await settle();

      expect(cart.stores()).toEqual([{ id: 1, name: 'Auchan' }]);
      expect(page.querySelector('.total')?.textContent).toContain('30,00 lei');
    });

    it('shows which store each product belongs to', async () => {
      await openWithTwoItems();
      answerOffers(offersFor);
      await settle();

      button('.plan-split').click();
      await settle();

      const stores = [...page.querySelectorAll('.row .store')].map((cell) => cell.textContent);
      expect(stores).toEqual(['Carrefour', 'Auchan']);
    });

    it('says how many products the single store lacks', async () => {
      await openWithTwoItems();

      answerOffers((id) => (id === 100 ? [lapteAuchan] : [untCarrefour]));
      await settle();

      expect(page.querySelector('.plan-single')?.textContent).toContain(
        `${ro.cart.missingPrefix} 1`,
      );
    });

    it('notes products that could not be compared', async () => {
      cart.add({ name: 'Mere', quantity: '1', price: '5' });
      await openWithTwoItems();

      answerOffers(offersFor);
      await settle();

      expect(page.textContent).toContain(ro.cart.notCompared);
    });

    it('compares again when a catalog product is added', async () => {
      await openWithTwoItems();
      answerOffers(offersFor);
      await settle();

      cart.add({ name: 'Ouă', quantity: '1', price: '9', sizeCategoryId: 300 });
      await settle();

      expect(
        http.match((request) => request.url === '/api/categories/300/products').length,
      ).toBe(1);
    });

    it('keeps the cart working when prices fail to load', async () => {
      await openWithTwoItems();

      http
        .match((request) => /\/products$/.test(request.url))
        .forEach((request) => request.flush(null, { status: 500, statusText: 'Error' }));
      await settle();

      expect(page.querySelector('.plans')).toBeNull();
      expect(page.querySelector('.total')?.textContent).toContain('30,00 lei');
    });

    it('drops the store link when a product is renamed to something unknown', async () => {
      cart.add({ name: 'Lapte', quantity: '1', price: '20', sizeCategoryId: 100 });
      cart.setStore(1, { id: 1, name: 'Auchan' }, 100);
      await open();

      button('.edit').click();
      await settle();
      buttons('.row')[0].click();
      await settle();
      type(page.querySelector<HTMLInputElement>('.edit-name')!, 'Ceva necunoscut');
      button('.save').click();
      http.expectOne((r) => r.url === '/api/search').flush([]);
      await settle();

      expect(cart.items()[0]).toMatchObject({
        storeId: null,
        storeName: null,
        sizeCategoryId: null,
      });
    });
  });

  describe('route', () => {
    const routeUrl = '/api/stores/route';
    const route: ShoppingRoute = {
      stops: [
        { store_id: 2, store_name: 'Carrefour', address: 'Strada 2', lat: 44.41, lng: 26.1, km: 0.8 },
        { store_id: 1, store_name: 'Auchan', address: 'Strada 1', lat: 44.5, lng: 26.1, km: 10.2 },
      ],
      total_km: 11,
      maps_url: 'https://maps.test/route',
    };

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

    function stopTexts(): string[] {
      return [...page.querySelectorAll('.route li')].map((stop) =>
        (stop.textContent ?? '').replace(/\s+/g, ' ').trim(),
      );
    }

    function mapsLink(): HTMLAnchorElement | null {
      return page.querySelector<HTMLAnchorElement>('a.maps-link');
    }

    beforeEach(async () => {
      vi.spyOn(window, 'open');
      cart.addProduct(auchan);
      cart.addProduct(carrefour);
      await open();
    });

    afterEach(() => vi.restoreAllMocks());

    it('is labelled as a route', () => {
      expect(button('.directions').textContent?.trim()).toBe(ro.cart.directions);
    });

    it('goes through every store in the cart, using the location', async () => {
      setLocation('allowed');

      button('.directions').click();
      const request = http.expectOne((r) => r.url === routeUrl);
      expect(request.request.params.getAll('store_ids')).toEqual(['1', '2']);
      expect(request.request.params.get('lat')).toBe('44.4');
      expect(request.request.params.get('lng')).toBe('26.1');
      request.flush(route);
      await settle();

      expect(stopTexts()).toEqual([
        'Carrefour · Strada 2 · 0,8 km',
        'Auchan · Strada 1 · 10,2 km',
      ]);
    });

    // Opening an empty tab first left phones on a blank page, so the app never leaves on its own.
    it('stays in the app and offers a Google Maps link to tap', async () => {
      setLocation('allowed');

      button('.directions').click();
      http.expectOne((r) => r.url === routeUrl).flush(route);
      await settle();

      expect(window.open).not.toHaveBeenCalled();
      const link = mapsLink()!;
      expect(link.href).toBe('https://maps.test/route');
      expect(link.target).toBe('_blank');
      expect(link.rel).toContain('noopener');
      expect(link.textContent?.trim()).toBe(ro.cart.openMaps);
    });

    it('turns the Traseu button into the Google Maps link, in the same place', async () => {
      setLocation('allowed');

      button('.directions').click();
      http.expectOne((r) => r.url === routeUrl).flush(route);
      await settle();

      expect(page.querySelector('button.directions')).toBeNull();
      expect(page.querySelectorAll('.maps-link').length).toBe(1);
    });

    it('asks again when the cart has different stores', async () => {
      setLocation('allowed');
      button('.directions').click();
      http.expectOne((r) => r.url === routeUrl).flush(route);
      await settle();

      cart.addProduct({ ...auchan, id: 7, store_id: 3, store_name: 'Kaufland' });
      await settle();

      expect(mapsLink()).toBeNull();
      expect(page.querySelector('.route')).toBeNull();
      expect(page.querySelector('button.directions')?.textContent?.trim()).toBe(
        ro.cart.directions,
      );
    });

    it('has no link before the route is known', async () => {
      setLocation('allowed');

      expect(mapsLink()).toBeNull();
      button('.directions').click();
      expect(mapsLink()).toBeNull();
      http.expectOne((r) => r.url === routeUrl).flush(route);
    });

    it('still works when location is denied, without a first distance', async () => {
      setLocation('denied');

      button('.directions').click();
      const request = http.expectOne((r) => r.url === routeUrl);
      expect(request.request.params.has('lat')).toBe(false);
      request.flush({ ...route, stops: [{ ...route.stops[0], km: null }, route.stops[1]] });
      await settle();

      expect(stopTexts()[0]).toBe('Carrefour · Strada 2');
      expect(mapsLink()?.href).toBe('https://maps.test/route');
    });

    it('explains a store without an address', async () => {
      setLocation('denied');

      button('.directions').click();
      fail(routeUrl, 404);
      await settle();

      expect(page.textContent).toContain(ro.cart.routeNoAddress);
      expect(page.querySelector('.route')).toBeNull();
      expect(mapsLink()).toBeNull();
    });

    it('explains a failure', async () => {
      setLocation('denied');

      button('.directions').click();
      fail(routeUrl, 500);
      await settle();

      expect(page.textContent).toContain(ro.cart.directionsFailed);
      expect(mapsLink()).toBeNull();
    });
  });

  describe('receipt', () => {
    const photo = new File(['x'], 'bon.jpg', { type: 'image/jpeg' });
    const readUrl = '/api/receipts/read';

    beforeEach(async () => {
      await open();
    });

    function upload(): void {
      pickFile('.receipt-input', photo);
    }

    async function read(reading: ReceiptReading): Promise<string> {
      upload();
      http.expectOne(readUrl).flush(reading);
      await settle();
      return page.querySelector('.receipt-result')?.textContent ?? '';
    }

    it('can be used with an empty cart', () => {
      expect(button('.scan').disabled).toBe(false);
    });

    // Without `capture`, the phone asks whether to take a photo or pick one from the gallery.
    it('lets the phone offer the camera or the gallery', () => {
      const input = page.querySelector('.receipt-input');

      expect(input?.getAttribute('accept')).toBe('image/*');
      expect(input?.hasAttribute('capture')).toBe(false);
    });

    it('has a single scan button', () => {
      expect(buttons('.scan').length).toBe(1);
      expect(page.querySelector('.gallery')).toBeNull();
    });

    it('sends the photo to be read', () => {
      upload();

      const request = http.expectOne(readUrl);
      expect((request.request.body as FormData).get('file')).toBe(photo);
      request.flush(receipt);
    });

    it('shows the shop, date and identifier', async () => {
      const result = await read(receipt);

      expect(result).toContain('Lidl');
      expect(result).toContain('26.10.2026 11:39');
      expect(result).toContain('Z 0347 / BF 0025');
      expect(result).not.toContain(ro.cart.receiptIdentifierGenerated);
    });

    it('shows every product with how many were bought', async () => {
      await read(receipt);

      const rows = [...page.querySelectorAll('.receipt-result tbody tr')].map((row) =>
        [...row.querySelectorAll('td')].map((cell) => cell.textContent?.trim()),
      );

      expect(rows).toEqual([
        ['Chips preparate manual', '2', '15,98 lei'],
        ['Banane', '0,734', '5,86 lei'],
      ]);
      expect(page.querySelector('.receipt-total')?.textContent).toContain('21,84 lei');
    });

    it('shows bottle deposits apart from the products', async () => {
      await read({ ...receipt, deposits: '1.50' });

      expect(page.querySelector('.receipt-deposits')?.textContent).toContain('1,50 lei');
      expect(page.querySelectorAll('.receipt-result tbody tr').length).toBe(2);
    });

    it('leaves out the deposits row when there are none', async () => {
      await read(receipt);

      expect(page.querySelector('.receipt-deposits')).toBeNull();
    });

    it('marks an identifier the app generated', async () => {
      const result = await read({ ...receipt, identifier: 'A1B2C3', identifier_printed: false });

      expect(result).toContain('A1B2C3');
      expect(result).toContain(ro.cart.receiptIdentifierGenerated);
    });

    it('says which details could not be read', async () => {
      await read(unreadFields);

      for (const field of ['.receipt-store', '.receipt-date', '.receipt-identifier', '.receipt-total']) {
        expect(page.querySelector(field)?.textContent).toContain(ro.cart.receiptNotRead);
      }
    });

    it('blocks a second upload while the first is running', async () => {
      upload();
      await settle();

      expect(button('.scan').disabled).toBe(true);
      http.expectOne(readUrl).flush(receipt);
    });

    it('shows the server reason a receipt was rejected', async () => {
      upload();

      fail(readUrl, 422, 'Motivul de la server');
      await settle();

      expect(page.textContent).toContain('Motivul de la server');
    });

    it('asks for a retake of an unreadable receipt', async () => {
      upload();

      fail(readUrl, 422);
      await settle();

      expect(page.textContent).toContain(ro.cart.receiptUnreadable);
    });

    it('does not blame the photo when the request itself failed', async () => {
      upload();

      fail(readUrl, 500);
      await settle();

      expect(page.textContent).toContain(ro.cart.receiptFailed);
      expect(page.textContent).not.toContain(ro.cart.receiptUnreadable);
    });

    it('can close the result', async () => {
      await read(receipt);

      button('.close-result').click();
      await settle();

      expect(page.querySelector('.receipt-result')).toBeNull();
    });
  });
});
