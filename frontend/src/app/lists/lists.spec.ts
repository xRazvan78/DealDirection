import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ShoppingList } from '../core/models';
import { ro } from '../shared/ro';
import { Lists } from './lists';

function list(id: number, name: string, state: ShoppingList['state']): ShoppingList {
  return { id, name, state, items: [] };
}

const saved: ShoppingList[] = [
  { ...list(1, 'Cumpărături săptămânale', 'draft'), items: [] },
  list(2, 'Plan alimentar', 'active'),
  list(3, 'Lista veche', 'completed'),
];
const serverError = { status: 500, statusText: 'Server Error' };

describe('Lists', () => {
  let fixture: ComponentFixture<Lists>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Lists],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Lists);
    page = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
  });

  async function load(lists: ShoppingList[] = saved): Promise<void> {
    http.expectOne('/api/lists').flush(lists);
    await fixture.whenStable();
  }

  function row(index: number): HTMLElement {
    return page.querySelectorAll<HTMLElement>('.list-row')[index];
  }

  function press(selector: string, index = 0): void {
    row(index).querySelector<HTMLButtonElement>(selector)!.click();
  }

  async function startRename(name: string): Promise<void> {
    press('.rename');
    await fixture.whenStable();
    const input = row(0).querySelector<HTMLInputElement>('input')!;
    input.value = name;
    input.dispatchEvent(new Event('input'));
    row(0).querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
  }

  it('shows a loading message first', () => {
    expect(page.textContent).toContain(ro.loading);

    http.expectOne('/api/lists').flush([]);
  });

  it('shows each list with its name and state', async () => {
    await load();

    expect(row(0).textContent).toContain('Cumpărături săptămânale');
    expect(row(0).textContent).toContain(ro.lists.states.draft);
    expect(row(1).textContent).toContain(ro.lists.states.active);
    expect(row(2).textContent).toContain(ro.lists.states.completed);
  });

  it('shows how many products a list has', async () => {
    const item = {
      id: 1,
      size_category_id: 100,
      chosen_product_id: null,
      brand: null,
      quantity: '1',
      removed: false,
    };
    await load([{ ...list(1, 'Lista', 'draft'), items: [item, { ...item, id: 2 }] }]);

    expect(row(0).textContent).toContain(`2 ${ro.lists.products}`);
  });

  it('uses the singular for one product', async () => {
    const item = {
      id: 1,
      size_category_id: 100,
      chosen_product_id: null,
      brand: null,
      quantity: '1',
      removed: false,
    };
    await load([{ ...list(1, 'Lista', 'draft'), items: [item] }]);

    expect(row(0).textContent).toContain(`1 ${ro.lists.product}`);
    expect(row(0).textContent).not.toContain(ro.lists.products);
  });

  it('opens a draft list in the cart', async () => {
    await load();

    expect(row(0).querySelector('a')?.getAttribute('href')).toBe('/cart/1');
  });

  it('opens an active list at its plan', async () => {
    await load();

    expect(row(1).querySelector('a')?.getAttribute('href')).toBe('/plan/2');
  });

  it('opens a completed list at its plan', async () => {
    await load();

    expect(row(2).querySelector('a')?.getAttribute('href')).toBe('/plan/3');
  });

  it('offers import when there are no lists', async () => {
    await load([]);

    expect(page.textContent).toContain(ro.lists.empty);
    expect(page.querySelector('.import')?.getAttribute('href')).toBe('/import');
  });

  it('always offers import', async () => {
    await load();

    expect(page.querySelector('.import')?.getAttribute('href')).toBe('/import');
  });

  it('shows a message when lists fail to load', async () => {
    http.expectOne('/api/lists').flush(null, serverError);
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.lists.loadFailed);
  });

  it('renames a list', async () => {
    await load();

    await startRename('  Lista nouă  ');
    const request = http.expectOne('/api/lists/1');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ name: 'Lista nouă' });
    request.flush(list(1, 'Lista nouă', 'draft'));
    await fixture.whenStable();

    expect(row(0).textContent).toContain('Lista nouă');
    expect(row(0).querySelector('input')).toBeNull();
  });

  it('starts a rename from the current name', async () => {
    await load();

    press('.rename');
    await fixture.whenStable();

    expect(row(0).querySelector<HTMLInputElement>('input')?.value).toBe(
      'Cumpărături săptămânale',
    );
  });

  it('does not save an empty name', async () => {
    await load();

    await startRename('   ');

    http.expectNone('/api/lists/1');
    expect(row(0).querySelector('input')).not.toBeNull();
  });

  it('cancels a rename', async () => {
    await load();
    press('.rename');
    await fixture.whenStable();

    press('.cancel');
    await fixture.whenStable();

    expect(row(0).querySelector('input')).toBeNull();
    expect(row(0).textContent).toContain('Cumpărături săptămânale');
  });

  it('keeps the old name when a rename fails', async () => {
    await load();

    await startRename('Lista nouă');
    http.expectOne('/api/lists/1').flush(null, serverError);
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.lists.saveFailed);
    expect(row(0).querySelector<HTMLInputElement>('input')?.value).toBe('Lista nouă');
  });

  it('deletes a list after confirming', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    await load();

    press('.delete', 1);
    const request = http.expectOne('/api/lists/2');
    expect(request.request.method).toBe('DELETE');
    request.flush(null);
    await fixture.whenStable();

    expect(confirm).toHaveBeenCalledWith(ro.lists.confirmDelete);
    expect(page.textContent).not.toContain('Plan alimentar');
  });

  it('keeps a list when the delete is not confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    await load();

    press('.delete');

    http.expectNone('/api/lists/1');
    expect(page.textContent).toContain('Cumpărături săptămânale');
  });

  it('keeps a list when deleting fails', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    await load();

    press('.delete');
    http.expectOne('/api/lists/1').flush(null, serverError);
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.lists.saveFailed);
    expect(page.textContent).toContain('Cumpărături săptămânale');
  });
});
