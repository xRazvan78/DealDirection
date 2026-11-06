import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { CartService } from '../cart/cart.service';
import { ro } from '../shared/ro';
import { Lists } from './lists';
import { SavedListsService } from './saved-lists.service';

describe('Lists', () => {
  let fixture: ComponentFixture<Lists>;
  let page: HTMLElement;
  let cart: CartService;
  let lists: SavedListsService;
  let navigate: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Lists],
      providers: [provideRouter([])],
    }).compileComponents();
    cart = TestBed.inject(CartService);
    lists = TestBed.inject(SavedListsService);
    navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
  });

  async function open(): Promise<void> {
    fixture = TestBed.createComponent(Lists);
    page = fixture.nativeElement;
    await fixture.whenStable();
  }

  async function press(selector: string): Promise<void> {
    page.querySelector<HTMLElement>(selector)!.click();
    await fixture.whenStable();
  }

  function saveList(name: string, products = 1): void {
    lists.startNew();
    for (let index = 0; index < products; index++) {
      cart.add({ name: `Produs ${index}`, quantity: '2', price: '5' });
    }
    lists.saveCurrent(name);
  }

  function names(): (string | null | undefined)[] {
    return [...page.querySelectorAll('.list-card .name')].map((name) => name.textContent?.trim());
  }

  it('explains when there are no lists', async () => {
    await open();

    expect(page.textContent).toContain(ro.lists.empty);
  });

  it('shows every saved list, not only the current one', async () => {
    saveList('Prima');
    saveList('A doua');
    await open();

    expect(names()).toEqual(['A doua', 'Prima']);
  });

  it('shows the number of products and the total', async () => {
    saveList('Prima', 2);
    await open();
    const details = page.querySelector('.list-card .details')?.textContent;

    expect(details).toContain(`2 ${ro.lists.products}`);
    expect(details).toContain('20,00 lei');
  });

  it('says 1 produs for a single product', async () => {
    saveList('Prima', 1);
    await open();

    expect(page.querySelector('.list-card .details')?.textContent).toContain(
      `1 ${ro.lists.product} `,
    );
  });

  it('marks the list that is open in the cart', async () => {
    saveList('Prima');
    saveList('A doua');
    await open();

    const cards = page.querySelectorAll('.list-card');
    expect(cards[0].textContent).toContain(ro.lists.openNow);
    expect(cards[1].textContent).not.toContain(ro.lists.openNow);
  });

  it('shows an unsaved cart at the top', async () => {
    cart.add({ name: 'Mere', quantity: '1', price: '1' });
    await open();

    expect(page.querySelector('.draft')?.textContent).toContain(ro.lists.unsavedCart);
  });

  it('opens the unsaved cart', async () => {
    cart.add({ name: 'Mere', quantity: '1', price: '1' });
    await open();

    await press('.draft');

    expect(navigate).toHaveBeenCalledWith('/cart');
    expect(cart.items().length).toBe(1);
  });

  it('opens a list in the cart page', async () => {
    saveList('Prima');
    const { id } = lists.lists()[0];
    lists.startNew();
    await open();

    await press('.open-list');

    expect(lists.current()?.id).toBe(id);
    expect(cart.items().length).toBe(1);
    expect(navigate).toHaveBeenCalledWith('/cart');
  });

  describe('with unsaved changes', () => {
    beforeEach(async () => {
      saveList('Prima');
      lists.startNew();
      cart.add({ name: 'Nesalvat', quantity: '1', price: '1' });
      await open();
    });

    it('asks before replacing them', async () => {
      await press('.open-list');

      expect(page.querySelector('.unsaved-warning')).not.toBeNull();
      expect(cart.items()[0].name).toBe('Nesalvat');
      expect(navigate).not.toHaveBeenCalled();
    });

    it('can save them first, then open the list', async () => {
      await press('.open-list');

      await press('.save-first');

      expect(lists.lists().map((list) => list.name)).toContain('Lista 1');
      expect(cart.items()[0].name).toBe('Produs 0');
      expect(navigate).toHaveBeenCalledWith('/cart');
    });

    it('can discard them and open the list', async () => {
      await press('.open-list');

      await press('.discard');

      expect(cart.items()[0].name).toBe('Produs 0');
      expect(lists.lists().length).toBe(1);
    });

    it('can be called off', async () => {
      await press('.open-list');

      await press('.keep-editing');

      expect(page.querySelector('.unsaved-warning')).toBeNull();
      expect(cart.items()[0].name).toBe('Nesalvat');
    });

    it('asks before starting a new list too', async () => {
      await press('.new-list');

      expect(page.querySelector('.unsaved-warning')).not.toBeNull();
      expect(cart.items().length).toBe(1);
    });
  });

  it('starts a new empty list', async () => {
    saveList('Prima');
    await open();

    await press('.new-list');

    expect(cart.items()).toEqual([]);
    expect(lists.current()).toBeNull();
    expect(navigate).toHaveBeenCalledWith('/cart');
  });

  it('renames a list', async () => {
    saveList('Veche');
    await open();

    await press('.rename');
    const input = page.querySelector<HTMLInputElement>('.rename-input')!;
    expect(input.value).toBe('Veche');
    input.value = 'Nouă';
    input.dispatchEvent(new Event('input'));
    page.querySelector('.rename-form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();

    expect(names()).toEqual(['Nouă']);
    expect(page.querySelector('.rename-form')).toBeNull();
  });

  it('can cancel a rename', async () => {
    saveList('Veche');
    await open();

    await press('.rename');
    await press('.cancel-rename');

    expect(page.querySelector('.rename-form')).toBeNull();
  });

  it('asks before deleting a list', async () => {
    saveList('Prima');
    await open();

    await press('.delete');

    expect(lists.lists().length).toBe(1);
    expect(page.textContent).toContain(ro.lists.confirmDelete);
  });

  it('deletes after confirming', async () => {
    saveList('Prima');
    await open();

    await press('.delete');
    await press('.confirm-delete');

    expect(lists.lists()).toEqual([]);
    expect(names()).toEqual([]);
  });

  it('can call off a delete', async () => {
    saveList('Prima');
    await open();

    await press('.delete');
    await press('.keep-list');

    expect(lists.lists().length).toBe(1);
    expect(page.querySelector('.confirm-delete')).toBeNull();
  });
});
