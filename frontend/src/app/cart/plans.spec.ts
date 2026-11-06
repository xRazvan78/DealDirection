import { Product } from '../core/models';
import { comparePlans } from './plans';

function offer(id: number, storeId: number, price: string): Product {
  return {
    id,
    store_id: storeId,
    store_name: storeId === 1 ? 'Auchan' : 'Carrefour',
    name: `Produs ${id}`,
    brand: null,
    price,
    image_url: null,
    updated_at: '2026-11-02T09:00:00Z',
  };
}

function item(id: number, sizeCategoryId: number | null, quantity = '1') {
  return { id, sizeCategoryId, quantity };
}

describe('comparePlans', () => {
  it('gives nothing for items with no catalog match', () => {
    expect(comparePlans([item(1, null)], new Map())).toBeNull();
    expect(comparePlans([item(1, 100)], new Map([[100, []]]))).toBeNull();
    expect(comparePlans([], new Map())).toBeNull();
  });

  it('picks the store with the lowest total as the single store', () => {
    const offers = new Map([
      [100, [offer(1, 1, '10'), offer(2, 2, '8')]],
      [200, [offer(3, 1, '10'), offer(4, 2, '9')]],
    ]);

    const result = comparePlans([item(1, 100), item(2, 200)], offers);

    expect(result?.single.storeName).toBe('Carrefour');
    expect(result?.single.total).toBe('17.00');
  });

  it('prefers the store with fewest missing items over a lower total', () => {
    const offers = new Map([
      [100, [offer(1, 1, '20'), offer(2, 2, '1')]],
      [200, [offer(3, 1, '20')]],
    ]);

    const result = comparePlans([item(1, 100), item(2, 200)], offers);

    expect(result?.single.storeName).toBe('Auchan');
    expect(result?.single.missing).toBe(0);
  });

  it('counts what the single store is missing', () => {
    const offers = new Map([
      [100, [offer(1, 1, '20')]],
      [200, [offer(2, 2, '20')]],
    ]);

    expect(comparePlans([item(1, 100), item(2, 200)], offers)?.single.missing).toBe(1);
  });

  it('breaks a tie with the lowest store id', () => {
    const offers = new Map([[100, [offer(1, 2, '5'), offer(2, 1, '5')]]]);

    expect(comparePlans([item(1, 100)], offers)?.single.storeName).toBe('Auchan');
  });

  it('uses the cheapest offer inside a store', () => {
    const offers = new Map([[100, [offer(1, 1, '9'), offer(2, 1, '5')]]]);

    expect(comparePlans([item(1, 100)], offers)?.single.total).toBe('5.00');
  });

  it('multiplies by quantity', () => {
    const offers = new Map([[100, [offer(1, 1, '2.50')]]]);

    expect(comparePlans([item(1, 100, '4')], offers)?.single.total).toBe('10.00');
  });

  it('shows a split that saves exactly 10 lei', () => {
    const offers = new Map([
      [100, [offer(1, 1, '20'), offer(2, 2, '10')]],
      [200, [offer(3, 1, '10'), offer(4, 2, '20')]],
    ]);

    const result = comparePlans([item(1, 100), item(2, 200)], offers);

    expect(result?.split?.total).toBe('20.00');
    expect(result?.saving).toBe('10.00');
    expect(result?.split?.lines.map(({ offer: chosen }) => chosen.store_id)).toEqual([2, 1]);
  });

  it('hides a split that saves 9.99', () => {
    const offers = new Map([
      [100, [offer(1, 1, '20'), offer(2, 2, '10.01')]],
      [200, [offer(3, 1, '9.99'), offer(4, 2, '20')]],
    ]);

    const result = comparePlans([item(1, 100), item(2, 200)], offers);

    expect(result?.saving).toBe('9.99');
    expect(result?.split).toBeNull();
  });

  it('hides a split that only uses one store', () => {
    const offers = new Map([[100, [offer(1, 1, '20'), offer(2, 2, '5')]]]);

    expect(comparePlans([item(1, 100)], offers)?.split).toBeNull();
  });

  it('measures the saving only over items the single store carries', () => {
    const offers = new Map([
      [100, [offer(1, 1, '20'), offer(2, 2, '30')]],
      [200, [offer(3, 1, '30'), offer(4, 2, '10')]],
      [300, [offer(5, 2, '100')]],
    ]);

    const result = comparePlans([item(1, 100), item(2, 200), item(3, 300)], offers);

    expect(result?.single.storeName).toBe('Carrefour');
    expect(result?.saving).toBe('10.00');
  });

  it('counts items that could not be compared', () => {
    const offers = new Map([[100, [offer(1, 1, '5')]]]);

    expect(comparePlans([item(1, 100), item(2, null)], offers)?.unmatched).toBe(1);
  });
});
