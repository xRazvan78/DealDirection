import { formatLei, formatQuantity, formatReceiptDate } from './format';

describe('formatQuantity', () => {
  it('shows a whole count without decimals', () => {
    expect(formatQuantity('2.000')).toBe('2');
    expect(formatQuantity('10')).toBe('10');
  });

  it('keeps the meaningful decimals of a weight', () => {
    expect(formatQuantity('0.734')).toBe('0,734');
    expect(formatQuantity('2.500')).toBe('2,5');
  });
});

describe('formatReceiptDate', () => {
  it('shows the date and time as printed', () => {
    expect(formatReceiptDate('2026-10-26T11:39:00')).toBe('26.10.2026 11:39');
  });

  it('leaves out a time that was not read', () => {
    expect(formatReceiptDate('2026-10-26T00:00:00')).toBe('26.10.2026');
  });
});

describe('formatLei', () => {
  it('uses a decimal comma and the lei suffix', () => {
    expect(formatLei('12.50')).toBe('12,50 lei');
  });

  it('always shows two decimals', () => {
    expect(formatLei('12.5')).toBe('12,50 lei');
    expect(formatLei('12')).toBe('12,00 lei');
  });

  it('keeps prices too precise for a float', () => {
    expect(formatLei('12345678901234567.10')).toBe('12345678901234567,10 lei');
  });
});
