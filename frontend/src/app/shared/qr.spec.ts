import { qrCode } from './qr';

describe('qrCode', () => {
  it('builds a square drawing for a code', () => {
    const qr = qrCode('DEMO-ABC123');

    expect(qr.size).toBeGreaterThan(20);
    expect(qr.path).toMatch(/^M\d+ \d+h1v1h-1z/);
  });

  it('gives the same drawing for the same code', () => {
    expect(qrCode('DEMO-ABC123')).toEqual(qrCode('DEMO-ABC123'));
  });

  it('gives a different drawing for a different code', () => {
    expect(qrCode('DEMO-ABC123').path).not.toBe(qrCode('DEMO-XYZ789').path);
  });
});
