import { TestBed } from '@angular/core/testing';
import { Product } from '../core/models';
import { CartItem, CartService } from './cart.service';

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

  it('counts the total quantity across products, keeping fractions exact', () => {
    const cart = create();

    expect(cart.itemCount()).toBe('0');

    cart.add({ name: 'Apă minerală', quantity: '5', price: '3' });
    cart.add({ name: 'Apă plată', quantity: '3', price: '2' });
    expect(cart.itemCount()).toBe('8');

    cart.add({ name: 'Mere', quantity: '0.1', price: '6' });
    cart.add({ name: 'Pere', quantity: '0.2', price: '7' });
    expect(cart.itemCount()).toBe('8.3');
  });

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

  it('remembers the catalog size of a product', () => {
    const cart = create();

    cart.addProduct(product, 100);

    expect(cart.items()[0].sizeCategoryId).toBe(100);
  });

  it('applies a chosen plan to the items it covers', () => {
    const cart = create();
    const item = cart.add({ name: 'Mere', quantity: '2', price: '9' });
    const other = cart.add({ name: 'Pere', quantity: '1', price: '4' });

    cart.applyPlan([{ itemId: item.id, offer: { ...product, price: '5' } }]);

    expect(cart.items()[0]).toMatchObject({
      name: 'Mere',
      quantity: '2',
      price: '5',
      storeName: 'Auchan',
    });
    expect(cart.items()[1]).toEqual(other);
  });

  it('lowers an item by one', () => {
    const cart = create();
    const item = cart.add({ name: 'Mere', quantity: '2', price: '1' });

    cart.decreaseItem(item.id);

    expect(cart.items()[0].quantity).toBe('1');
  });

  it('removes an item that runs out', () => {
    const cart = create();
    const item = cart.add({ name: 'Mere', quantity: '1', price: '1' });

    cart.decreaseItem(item.id);

    expect(cart.items()).toEqual([]);
  });

  it('reports how much of a product is in the cart', () => {
    const cart = create();
    expect(cart.quantityOf(product)).toBeNull();

    cart.addProduct(product);
    cart.addProduct(product);

    expect(cart.quantityOf(product)).toBe('2');
  });

  it('lowers a product by one', () => {
    const cart = create();
    cart.addProduct(product);
    cart.addProduct(product);

    cart.decreaseProduct(product);

    expect(cart.quantityOf(product)).toBe('1');
  });

  it('removes a product when its quantity runs out', () => {
    const cart = create();
    cart.addProduct(product);

    cart.decreaseProduct(product);

    expect(cart.items()).toEqual([]);
  });

  it('keeps the count when a plan moves a product to another store', () => {
    const cart = create();
    cart.addProduct(product);
    const other = { ...product, id: 9, store_id: 2, store_name: 'Carrefour', name: 'Alt nume' };

    cart.applyPlan([{ itemId: cart.items()[0].id, offer: other }]);

    expect(cart.quantityOf(other)).toBe('1');
    expect(cart.quantityOf(product)).toBeNull();
  });

  it('still finds items saved before products had an id', () => {
    const cart = create();
    const { productId: _unused, ...oldItem } = cart.add({
      name: product.name,
      quantity: '3',
      price: '1',
      store: { id: product.store_id, name: product.store_name },
    });
    cart.replace([oldItem as CartItem]);

    expect(cart.quantityOf(product)).toBe('3');
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
