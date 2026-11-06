import { TestBed } from '@angular/core/testing';
import { Product } from '../core/models';
import { CartService } from './cart.service';

const product: Product = {
  id: 5,
  store_id: 1,
  store_name: 'Auchan',
  name: 'Lapte 3.5% 1 l',
  brand: null,
  price: '8.50',
  image_url: null,
  updated_at: '2026-11-02T09:00:00Z',
};

describe('CartService', () => {
  beforeEach(() => localStorage.clear());

  function create(): CartService {
    return TestBed.inject(CartService);
  }

  it('adds typed products, with no store yet', () => {
    const cart = create();

    const item = cart.add({ name: 'Mere', quantity: '2', price: '3.50' });

    expect(cart.items()).toEqual([item]);
    expect(item.storeId).toBeNull();
  });

  it('gives every item its own id', () => {
    const cart = create();

    const first = cart.add({ name: 'Mere', quantity: '1', price: '1' });
    const second = cart.add({ name: 'Pere', quantity: '1', price: '1' });

    expect(first.id).not.toBe(second.id);
  });

  it('works out the total and the points', () => {
    const cart = create();

    cart.add({ name: 'Mere', quantity: '2', price: '5' });

    expect(cart.total()).toBe('10.00');
    expect(cart.points()).toBe(100);
  });

  it('adds a catalog product with its store', () => {
    const cart = create();

    cart.addProduct(product);

    expect(cart.items()[0]).toMatchObject({
      name: 'Lapte 3.5% 1 l',
      quantity: '1',
      price: '8.50',
      storeId: 1,
      storeName: 'Auchan',
    });
  });

  it('raises the quantity when the same product is added again', () => {
    const cart = create();

    cart.addProduct(product);
    cart.addProduct(product);

    expect(cart.items().length).toBe(1);
    expect(cart.items()[0].quantity).toBe('2');
  });

  it('lists each store once', () => {
    const cart = create();

    cart.addProduct(product);
    cart.addProduct({ ...product, id: 6, name: 'Unt' });
    cart.addProduct({ ...product, id: 7, store_id: 2, store_name: 'Carrefour' });

    expect(cart.stores()).toEqual([
      { id: 1, name: 'Auchan' },
      { id: 2, name: 'Carrefour' },
    ]);
  });

  it('sets a store on an item later', () => {
    const cart = create();
    const item = cart.add({ name: 'Mere', quantity: '1', price: '1' });

    cart.setStore(item.id, { id: 2, name: 'Carrefour' });

    expect(cart.stores()).toEqual([{ id: 2, name: 'Carrefour' }]);
  });

  it('keeps the cart after a reload', () => {
    create().add({ name: 'Mere', quantity: '2', price: '3.50' });
    TestBed.resetTestingModule();

    expect(create().items()[0].name).toBe('Mere');
  });

  it('survives damaged saved data', () => {
    localStorage.setItem('dealdirection.cart', '{broken');

    expect(create().items()).toEqual([]);
  });

  it('clears everything', () => {
    const cart = create();
    cart.add({ name: 'Mere', quantity: '2', price: '3.50' });

    cart.clear();

    expect(cart.items()).toEqual([]);
    expect(localStorage.getItem('dealdirection.cart')).toBeNull();
  });
});
