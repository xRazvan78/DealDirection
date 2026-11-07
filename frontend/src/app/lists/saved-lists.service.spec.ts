import { TestBed } from '@angular/core/testing';
import { CartService } from '../cart/cart.service';
import { setLanguage } from '../shared/language';
import { SavedListsService } from './saved-lists.service';

describe('SavedListsService', () => {
  let cart: CartService;
  let lists: SavedListsService;

  function setup(): void {
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

  it('clears everything', () => {
    addItem();
    lists.saveCurrent('Veche');

    lists.clear();

    expect(lists.lists()).toEqual([]);
    expect(localStorage.getItem('dealdirection.lists')).toBeNull();
  });
});
