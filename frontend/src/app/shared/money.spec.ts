import {
  addQuantities,
  compareAmounts,
  isPrice,
  isQuantity,
  normalizeAmount,
  pointsFor,
  subtractAmounts,
  totalOf,
} from './money';

describe('money', () => {
  it('compares amounts exactly', () => {
    expect(compareAmounts('9.99', '10')).toBeLessThan(0);
    expect(compareAmounts('10.00', '10')).toBe(0);
    expect(compareAmounts('10.01', '10')).toBeGreaterThan(0);
  });

  it('subtracts amounts exactly', () => {
    expect(subtractAmounts('0.30', '0.10')).toBe('0.20');
    expect(subtractAmounts('30', '20')).toBe('10.00');
  });

  it('accepts a decimal comma', () => {
    expect(normalizeAmount(' 8,50 ')).toBe('8.50');
  });

  it('checks prices', () => {
    expect(isPrice('8.50')).toBe(true);
    expect(isPrice('0')).toBe(true);
    expect(isPrice('8.505')).toBe(false);
    expect(isPrice('abc')).toBe(false);
    expect(isPrice('')).toBe(false);
  });

  it('checks quantities, which must be above zero', () => {
    expect(isQuantity('2')).toBe(true);
    expect(isQuantity('0.734')).toBe(true);
    expect(isQuantity('0')).toBe(false);
    expect(isQuantity('0.000')).toBe(false);
    expect(isQuantity('1.2345')).toBe(false);
  });

  it('multiplies each price by its quantity and sums the lines', () => {
    const lines = [
      { price: '8.50', quantity: '2' },
      { price: '4.50', quantity: '1' },
    ];

    expect(totalOf(lines)).toBe('21.50');
  });

  it('adds without float errors', () => {
    const lines = [
      { price: '0.10', quantity: '1' },
      { price: '0.20', quantity: '1' },
    ];

    expect(totalOf(lines)).toBe('0.30');
  });

  it('rounds a weighed total half up to the nearest ban', () => {
    expect(totalOf([{ price: '7.99', quantity: '0.734' }])).toBe('5.86');
    expect(totalOf([{ price: '0.05', quantity: '0.1' }])).toBe('0.01');
  });

  it('gives zero for an empty list', () => {
    expect(totalOf([])).toBe('0.00');
  });

  it('gives 100 points for 10 lei', () => {
    expect(pointsFor('10.00')).toBe(100);
    expect(pointsFor('21.50')).toBe(215);
    expect(pointsFor('0.00')).toBe(0);
  });

  it('rounds points half up', () => {
    expect(pointsFor('1.05')).toBe(11);
    expect(pointsFor('1.04')).toBe(10);
  });

  it('adds quantities exactly', () => {
    expect(addQuantities('0.1', '0.2')).toBe('0.3');
    expect(addQuantities('1', '1')).toBe('2');
  });
});
