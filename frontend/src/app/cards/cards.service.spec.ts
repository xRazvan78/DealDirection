import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CardBrand, CardScan, LoyaltyCard } from '../core/models';
import { CardsService } from './cards.service';

const brands: CardBrand[] = [
  { id: 'lidl', name: 'Lidl', colour: '#0050aa' },
  { id: 'kaufland', name: 'Kaufland', colour: '#e10915' },
];
const lidl: LoyaltyCard = {
  id: 1,
  brand: 'lidl',
  name: 'Lidl',
  colour: '#0050aa',
  code_text: '4812345678901',
  code_format: 'qr',
  image: 'data:image/svg+xml;base64,AAAA',
};
const scan: CardScan = {
  code_text: '2401234567891',
  code_format: 'ean13',
  image: 'data:image/svg+xml;base64,BBBB',
  suggested_brand: 'kaufland',
};

describe('CardsService', () => {
  let http: HttpTestingController;
  let service: CardsService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    service = TestBed.inject(CardsService);
  });

  afterEach(() => http.verify());

  function loaded(cards: LoyaltyCard[] = [lidl]): void {
    service.load();
    http.expectOne('/api/card-brands').flush(brands);
    http.expectOne('/api/cards').flush(cards);
  }

  it('loads the brands and the account cards', () => {
    loaded();

    expect(service.brands()).toEqual(brands);
    expect(service.cards()).toEqual([lidl]);
  });

  it('loads the brands only once', () => {
    loaded();

    service.load();

    http.expectNone('/api/card-brands');
    http.expectOne('/api/cards').flush([lidl]);
  });

  it('sends a photo to be scanned', () => {
    const photo = new File(['x'], 'card.jpg', { type: 'image/jpeg' });
    let result: CardScan | undefined;

    service.scan(photo).subscribe((found) => (result = found));
    const request = http.expectOne('/api/cards/scan');
    expect((request.request.body as FormData).get('file')).toBe(photo);
    request.flush(scan);

    expect(result).toEqual(scan);
  });

  it('saves a scanned code under the chosen brand', () => {
    loaded([]);

    service.add('kaufland', { scan }).subscribe();
    const request = http.expectOne('/api/cards');
    const body = request.request.body as FormData;
    expect([body.get('brand'), body.get('code_text'), body.get('code_format'), body.get('file')]).toEqual([
      'kaufland',
      '2401234567891',
      'ean13',
      null,
    ]);
    request.flush({ ...lidl, id: 2, brand: 'kaufland', name: 'Kaufland' });

    expect(service.cards().map((card) => card.brand)).toEqual(['kaufland']);
  });

  it('saves the photo itself when no code was read', () => {
    loaded([]);
    const photo = new File(['x'], 'card.jpg', { type: 'image/jpeg' });

    service.add('lidl', { photo }).subscribe();
    const body = http.expectOne('/api/cards').request.body as FormData;

    expect([body.get('brand'), body.get('file'), body.get('code_text')]).toEqual(['lidl', photo, null]);
  });

  it('removes a deleted card', () => {
    loaded();

    service.remove(1).subscribe();
    http.expectOne({ method: 'DELETE', url: '/api/cards/1' }).flush(null);

    expect(service.cards()).toEqual([]);
  });

  it('knows which brands already have a card', () => {
    loaded();

    expect(service.hasBrand('lidl')).toBe(true);
    expect(service.hasBrand('kaufland')).toBe(false);
  });

  it('clears the cards on logout', () => {
    loaded();

    service.clear();

    expect(service.cards()).toEqual([]);
  });
});
