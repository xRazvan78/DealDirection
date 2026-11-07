import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CartService } from '../cart/cart.service';
import { ReceiptReading, StoredList } from '../core/models';
import { setLanguage } from '../shared/language';
import { SavedListsService } from './saved-lists.service';

const receipt: ReceiptReading = {
  store_name: 'Kaufland',
  purchased_at: '2026-11-06T12:37:00',
  identifier: '123',
  identifier_printed: true,
  total: '10.00',
  deposits: '0',
  lines: [{ name: 'MERE', quantity: '2', line_total: '10.00' }],
};

describe('SavedListsService', () => {
  let cart: CartService;
  let lists: SavedListsService;
  let http: HttpTestingController;

  function setup(): void {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    cart = TestBed.inject(CartService);
    lists = TestBed.inject(SavedListsService);
  }

  beforeEach(() => {
    localStorage.clear();
    setup();
  });

  function addItem(name = 'Mere'): void {
    cart.add({ name, quantity: '2', price: '5' });
  }

  it('saves the cart under the given name', () => {
    addItem();

    lists.saveCurrent('  Cumpărături  ');

    expect(lists.lists()[0]).toMatchObject({ name: 'Cumpărături' });
    expect(lists.lists()[0].items[0].name).toBe('Mere');
  });

  it('names a list Lista 1 when no name is given', () => {
    addItem();

    lists.saveCurrent('');

    expect(lists.lists()[0].name).toBe('Lista 1');
  });

  it('names a list List 1 in English', () => {
    setLanguage('en');
    addItem();

    lists.saveCurrent('');
    setLanguage('ro');

    expect(lists.lists()[0].name).toBe('List 1');
  });

  it('numbers default names without repeating one', () => {
    addItem();
    lists.saveCurrent('');
    lists.startNew();
    addItem();
    lists.saveCurrent('   ');
    lists.remove(lists.lists()[0].id);
    lists.startNew();
    addItem();

    lists.saveCurrent('');

    expect(lists.lists().map((list) => list.name).sort()).toEqual(['Lista 1', 'Lista 2']);
  });

  it('suggests the next free default name', () => {
    expect(lists.nextDefaultName()).toBe('Lista 1');
    addItem();
    lists.saveCurrent('');

    expect(lists.nextDefaultName()).toBe('Lista 2');
  });

  it('treats the saved list as the current one', () => {
    addItem();

    lists.saveCurrent('Săptămâna');

    expect(lists.current()?.name).toBe('Săptămâna');
    expect(lists.unsaved()).toBe(false);
  });

  it('notices changes after saving', () => {
    addItem();
    lists.saveCurrent('Săptămâna');

    addItem('Pere');

    expect(lists.unsaved()).toBe(true);
  });

  it('updates the open list instead of creating another', () => {
    addItem();
    lists.saveCurrent('Săptămâna');
    addItem('Pere');

    lists.saveCurrent();

    expect(lists.lists().length).toBe(1);
    expect(lists.lists()[0].name).toBe('Săptămâna');
    expect(lists.lists()[0].items.length).toBe(2);
  });

  it('has nothing to save for an empty cart', () => {
    expect(lists.unsaved()).toBe(false);
  });

  it('loads a list into the cart when opened', () => {
    addItem();
    lists.saveCurrent('Prima');
    const { id } = lists.lists()[0];
    lists.startNew();
    expect(cart.items()).toEqual([]);

    lists.open(id);

    expect(cart.items()[0].name).toBe('Mere');
    expect(lists.current()?.id).toBe(id);
    expect(lists.unsaved()).toBe(false);
  });

  it('keeps old lists when a new one is started', () => {
    addItem();
    lists.saveCurrent('Prima');

    lists.startNew();
    addItem('Pere');
    lists.saveCurrent('A doua');

    expect(lists.lists().map((list) => list.name).sort()).toEqual(['A doua', 'Prima']);
  });

  it('renames a list', () => {
    addItem();
    lists.saveCurrent('Veche');

    lists.rename(lists.lists()[0].id, ' Nouă ');

    expect(lists.lists()[0].name).toBe('Nouă');
  });

  it('ignores a blank rename', () => {
    addItem();
    lists.saveCurrent('Veche');

    lists.rename(lists.lists()[0].id, '   ');

    expect(lists.lists()[0].name).toBe('Veche');
  });

  it('keeps the cart when its list is deleted, as unsaved', () => {
    addItem();
    lists.saveCurrent('Veche');

    lists.remove(lists.lists()[0].id);

    expect(lists.lists()).toEqual([]);
    expect(cart.items().length).toBe(1);
    expect(lists.current()).toBeNull();
    expect(lists.unsaved()).toBe(true);
  });

  it('keeps lists and the open list after a reload', () => {
    addItem();
    lists.saveCurrent('Păstrată');
    TestBed.resetTestingModule();

    setup();

    expect(lists.lists()[0].name).toBe('Păstrată');
    expect(lists.current()?.name).toBe('Păstrată');
    expect(lists.unsaved()).toBe(false);
  });

  it('survives damaged saved data', () => {
    TestBed.resetTestingModule();
    localStorage.setItem('dealdirection.lists', '{broken');

    setup();

    expect(lists.lists()).toEqual([]);
  });

  describe('with a receipt', () => {
    it('saves a new list and empties the cart', () => {
      addItem();

      lists.finish(receipt, 1403);

      expect(lists.lists()[0]).toMatchObject({ name: 'Lista 1', receipt });
      expect(lists.lists()[0].items[0].name).toBe('Mere');
      expect(cart.items()).toEqual([]);
      expect(lists.current()).toBeNull();
      expect(lists.unsaved()).toBe(false);
    });

    it('keeps the latest changes to an open list', () => {
      addItem();
      lists.saveCurrent('Săptămâna');
      addItem('Pere');

      lists.finish(receipt, 1403);

      expect(lists.lists().length).toBe(1);
      expect(lists.lists()[0].name).toBe('Săptămâna');
      expect(lists.lists()[0].items.length).toBe(2);
    });

    it('never goes back in the cart', () => {
      addItem();
      lists.finish(receipt, 1403);

      lists.open(lists.lists()[0].id);

      expect(cart.items()).toEqual([]);
      expect(lists.current()).toBeNull();
    });

    it('can no longer be renamed', () => {
      addItem();
      lists.finish(receipt, 1403);

      lists.rename(lists.lists()[0].id, 'Nouă');

      expect(lists.lists()[0].name).toBe('Lista 1');
    });

    it('can be deleted', () => {
      addItem();
      lists.finish(receipt, 1403);

      lists.remove(lists.lists()[0].id);

      expect(lists.lists()).toEqual([]);
    });

    it('stays closed after a reload', () => {
      addItem();
      lists.finish(receipt, 1403);
      TestBed.resetTestingModule();

      setup();

      expect(lists.lists()[0].receipt).toEqual(receipt);
      expect(cart.items()).toEqual([]);
    });
  });

  describe('between devices', () => {
    const url = '/api/saved-lists';
    const stored = (changes: Partial<StoredList> = {}): StoredList => ({
      id: 7,
      name: 'De pe telefon',
      items: [],
      updated_at: '2026-11-07T10:00:00Z',
      receipt: null,
      points: null,
      ...changes,
    });

    function answerPut(changes: Partial<StoredList> = {}): void {
      const request = http.expectOne((sent) => sent.method === 'PUT');
      request.flush({ ...(request.request.body as StoredList), ...changes });
    }

    it('sends a saved list to the backend', () => {
      addItem();

      lists.saveCurrent('Prima');

      const { request } = http.expectOne((sent) => sent.method === 'PUT');
      expect(request.url).toBe(`${url}/${lists.lists()[0].id}`);
      expect(request.body).toMatchObject({ name: 'Prima', receipt: null });
      expect(lists.lists()[0].synced).toBe(false);
    });

    it('remembers when the backend has the list', () => {
      addItem();
      lists.saveCurrent('Prima');

      answerPut();

      expect(lists.lists()[0].synced).toBe(true);
    });

    it('does not lose a change made while the last one was being sent', () => {
      addItem();
      lists.saveCurrent('Prima');
      const first = http.expectOne((sent) => sent.method === 'PUT');
      addItem('Pere');
      lists.saveCurrent();

      first.flush(first.request.body);

      expect(lists.lists()[0].items.length).toBe(2);
      expect(lists.lists()[0].synced).toBe(false);
    });

    it('sends the receipt and its points', () => {
      addItem();

      lists.finish(receipt, 120);

      const sent = http.match((request) => request.method === 'PUT').map(({ request }) => request);
      expect(sent.at(-1)?.body).toMatchObject({ receipt, points: 120 });
    });

    it('deletes a list on the backend too', () => {
      addItem();
      lists.saveCurrent('Prima');
      const { id } = lists.lists()[0];

      lists.remove(id);

      http.expectOne({ method: 'DELETE', url: `${url}/${id}` });
    });

    it('shows lists saved on another device', () => {
      lists.sync();

      http.expectOne(url).flush([stored()]);

      expect(lists.lists()).toMatchObject([{ id: 7, name: 'De pe telefon', synced: true }]);
    });

    it('sends lists saved before they were shared', () => {
      localStorage.setItem(
        'dealdirection.lists',
        JSON.stringify([{ id: 1, name: 'Veche', items: [], updatedAt: '2026-11-01T10:00:00Z' }]),
      );
      TestBed.resetTestingModule();
      setup();

      lists.sync();
      http.expectOne(url).flush([]);

      expect(http.expectOne((sent) => sent.method === 'PUT').request.body).toMatchObject({
        name: 'Veche',
      });
    });

    it('drops a list deleted on another device', () => {
      addItem();
      lists.saveCurrent('Prima');
      answerPut();

      lists.sync();
      http.expectOne(url).flush([]);

      expect(lists.lists()).toEqual([]);
    });

    it('takes in a change made on another device', () => {
      addItem();
      lists.saveCurrent('Prima');
      answerPut();
      const { id } = lists.lists()[0];

      lists.sync();
      http.expectOne(url).flush([stored({ id, name: 'Redenumită' })]);

      expect(lists.lists().map((list) => list.name)).toEqual(['Redenumită']);
    });

    it('keeps the cart as unsaved when another device finished its list', () => {
      addItem();
      lists.saveCurrent('Prima');
      answerPut();
      const { id } = lists.lists()[0];

      lists.sync();
      http.expectOne(url).flush([stored({ id, receipt, points: 50 })]);

      expect(lists.current()).toBeNull();
      expect(cart.items().length).toBe(1);
      expect(lists.unsaved()).toBe(true);
    });

    it('keeps working without a connection', () => {
      addItem();
      lists.saveCurrent('Prima');
      http
        .expectOne((sent) => sent.method === 'PUT')
        .flush(null, { status: 503, statusText: 'Offline' });

      lists.sync();
      http.expectOne(url).flush(null, { status: 503, statusText: 'Offline' });

      expect(lists.lists()[0]).toMatchObject({ name: 'Prima', synced: false });
    });
  });

  it('clears everything', () => {
    addItem();
    lists.saveCurrent('Veche');

    lists.clear();

    expect(lists.lists()).toEqual([]);
    expect(localStorage.getItem('dealdirection.lists')).toBeNull();
  });
});
