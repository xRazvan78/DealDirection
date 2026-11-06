import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CardBrand, CardScan, LoyaltyCard } from '../core/models';
import { ro } from '../shared/ro';
import { Cards } from './cards';

const brands: CardBrand[] = [
  { id: 'lidl', name: 'Lidl', colour: '#0050aa' },
  { id: 'kaufland', name: 'Kaufland', colour: '#e10915' },
  { id: 'auchan', name: 'Auchan', colour: '#d6001c' },
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
const photo = new File(['x'], 'card.jpg', { type: 'image/jpeg' });

describe('Cards', () => {
  let fixture: ComponentFixture<Cards>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Cards],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    URL.createObjectURL = vi.fn(() => 'blob:card-photo');
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
  });

  async function open(cards: LoyaltyCard[] = []): Promise<void> {
    fixture = TestBed.createComponent(Cards);
    page = fixture.nativeElement;
    fixture.detectChanges();
    http.expectOne('/api/card-brands').flush(brands);
    http.expectOne('/api/cards').flush(cards);
    await settle();
  }

  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    fixture.detectChanges();
    await fixture.whenStable();
  }

  function el<T extends HTMLElement = HTMLElement>(selector: string): T | null {
    return page.querySelector<T>(selector);
  }

  async function press(selector: string): Promise<void> {
    el<HTMLButtonElement>(selector)!.click();
    await settle();
  }

  async function pick(file: File): Promise<void> {
    await press('.add-card');
    const input = el<HTMLInputElement>('.photo-input')!;
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await settle();
  }

  async function choose(brand: string): Promise<void> {
    const radio = el<HTMLInputElement>(`input[value="${brand}"]`)!;
    radio.checked = true;
    radio.dispatchEvent(new Event('change'));
    await settle();
  }

  async function submit(): Promise<void> {
    el('.new-card')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  it('lists the account cards in their brand colours', async () => {
    await open([lidl]);

    const card = el<HTMLButtonElement>('.card')!;
    expect(card.textContent).toContain('Lidl');
    expect(card.style.background).toContain('rgb(0, 80, 170)');
    expect(card.querySelector('img')!.getAttribute('src')).toBe(lidl.image);
  });

  it('says how to add a first card', async () => {
    await open();

    expect(el('.note')!.textContent).toContain(ro.cards.empty);
  });

  it('scans the code first, then saves it under the chosen brand', async () => {
    await open();

    await pick(photo);
    const request = http.expectOne('/api/cards/scan');
    expect((request.request.body as FormData).get('file')).toBe(photo);
    request.flush(scan);
    await settle();

    expect(el<HTMLImageElement>('.preview')!.getAttribute('src')).toBe(scan.image);
    expect(el('.code-text')!.textContent).toContain('2401234567891');
    // The brand printed on the card is pre-selected.
    expect(el<HTMLInputElement>('input[value="kaufland"]')!.checked).toBe(true);

    await submit();
    const save = http.expectOne('/api/cards');
    expect((save.request.body as FormData).get('brand')).toBe('kaufland');
    save.flush({ ...lidl, id: 2, brand: 'kaufland', name: 'Kaufland', colour: '#e10915' });
    await settle();

    expect(el('.new-card')).toBeNull();
    expect(Array.from(page.querySelectorAll('.card')).map((c) => c.textContent?.trim())).toEqual(['Kaufland']);
  });

  it('lets the client change the suggested brand', async () => {
    await open();
    await pick(photo);
    http.expectOne('/api/cards/scan').flush(scan);
    await settle();

    await choose('auchan');
    await submit();

    expect((http.expectOne('/api/cards').request.body as FormData).get('brand')).toBe('auchan');
  });

  it('asks for a brand when none is suggested', async () => {
    await open();
    await pick(photo);
    http.expectOne('/api/cards/scan').flush({ ...scan, suggested_brand: null });
    await settle();

    await submit();

    expect(el('.error')!.textContent).toContain(ro.cards.brandRequired);
    http.expectNone('/api/cards');
  });

  it('disables brands that already have a card, even if suggested', async () => {
    await open([lidl]);
    await pick(photo);
    http.expectOne('/api/cards/scan').flush({ ...scan, suggested_brand: 'lidl' });
    await settle();

    const taken = el<HTMLInputElement>('input[value="lidl"]')!;
    expect(taken.disabled).toBe(true);
    expect(taken.checked).toBe(false);
    expect(taken.closest('label')!.textContent).toContain(ro.cards.alreadySaved);
  });

  it('offers to save the photo when no code is found', async () => {
    await open();
    await pick(photo);
    http
      .expectOne('/api/cards/scan')
      .flush({ detail: 'Nu am găsit niciun cod QR sau cod de bare.' }, { status: 422, statusText: 'Unprocessable' });
    await settle();

    expect(el('.error')!.textContent).toContain('Nu am găsit niciun cod QR');

    await press('.save-photo');
    expect(el<HTMLImageElement>('.preview')!.getAttribute('src')).toBe('blob:card-photo');
    expect(el('.new-card')!.textContent).toContain(ro.cards.photoOnly);

    await choose('lidl');
    await submit();
    const body = http.expectOne('/api/cards').request.body as FormData;
    expect([body.get('brand'), body.get('file'), body.get('code_text')]).toEqual(['lidl', photo, null]);
  });

  it('shows the backend message when a brand already has a card', async () => {
    await open();
    await pick(photo);
    http.expectOne('/api/cards/scan').flush(scan);
    await settle();

    await submit();
    http
      .expectOne('/api/cards')
      .flush({ detail: 'Ai deja un card Kaufland. Șterge-l mai întâi.' }, { status: 409, statusText: 'Conflict' });
    await settle();

    expect(el('.error')!.textContent).toContain('Ai deja un card Kaufland');
    expect(el('.new-card')).not.toBeNull();
  });

  it('rejects a file that is not a photo without sending it', async () => {
    await open();

    await pick(new File(['%PDF'], 'card.pdf', { type: 'application/pdf' }));

    expect(el('.error')!.textContent).toContain(ro.cards.wrongFile);
    http.expectNone('/api/cards/scan');
  });

  it('cancelling discards the scanned code', async () => {
    await open();
    await pick(photo);
    http.expectOne('/api/cards/scan').flush(scan);
    await settle();

    await press('.cancel-card');

    expect(el('.new-card')).toBeNull();
    http.expectNone('/api/cards');
  });

  it('shows a card full screen with its code, and deletes it after confirming', async () => {
    await open([lidl]);

    await press('.card');
    const view = el('.card-view')!;
    expect(view.querySelector('img')!.getAttribute('src')).toBe(lidl.image);
    expect(view.textContent).toContain('4812345678901');

    await press('.delete-card');
    expect(el('.question')!.textContent).toContain(ro.cards.confirmDelete);
    await press('.confirm-delete');
    http.expectOne({ method: 'DELETE', url: '/api/cards/1' }).flush(null);
    await settle();

    expect(el('.card-view')).toBeNull();
    expect(el('.card')).toBeNull();
  });
});
