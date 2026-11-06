import { formatLei } from './format';

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
