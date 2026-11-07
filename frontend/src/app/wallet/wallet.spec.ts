import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Reward, Voucher, Wallet as WalletData } from '../core/models';
import { ro } from '../shared/ro';
import { Wallet } from './wallet';

const wallet: WalletData = {
  balance: 1250,
  history: [
    { amount: 418, reason: 'Bon Auchan', created_at: '2026-11-05T10:00:00Z' },
    { amount: -500, reason: 'Cafea', created_at: '2026-11-04T10:00:00Z' },
  ],
};
const rewards: Reward[] = [
  { id: 1, name: 'Cafea', cost: 500, store_name: 'Auchan' },
  { id: 2, name: 'Reducere 50 lei', cost: 5000, store_name: 'Carrefour' },
];
const voucher: Voucher = {
  id: 7,
  code: 'DEMO-ABC123',
  reward_name: 'Cafea',
  store_name: 'Auchan',
  expires_at: '2026-12-06T10:00:00Z',
};

describe('Wallet (Point Shop)', () => {
  let fixture: ComponentFixture<Wallet>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Wallet],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Wallet);
    page = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  async function settle(): Promise<void> {
    await fixture.whenStable();
  }

  async function load(data = wallet, vouchers: Voucher[] = []): Promise<void> {
    http.expectOne('/api/wallet').flush(data);
    http.expectOne('/api/rewards').flush(rewards);
    http.expectOne('/api/vouchers').flush(vouchers);
    await settle();
  }

  function redeemButtons(): HTMLButtonElement[] {
    return [...page.querySelectorAll<HTMLButtonElement>('.reward button')];
  }

  async function redeemFirst(): Promise<void> {
    await load();
    redeemButtons()[0].click();
    http.expectOne({ method: 'POST', url: '/api/rewards/1/redeem' }).flush(voucher);
    http.expectOne('/api/wallet').flush({ ...wallet, balance: 750 });
    await settle();
  }

  it('shows a loading message first', async () => {
    expect(page.textContent).toContain(ro.loading);

    await load();
  });

  it('is titled Point Shop', async () => {
    await load();

    expect(page.querySelector('h1')?.textContent).toContain(ro.wallet.title);
  });

  it('shows the points balance', async () => {
    await load();

    expect(page.querySelector('.balance')?.textContent).toContain('1250');
  });

  it('lists each reward with its cost', async () => {
    await load();
    const first = page.querySelector('.reward')?.textContent;

    expect(first).toContain('Cafea');
    expect(first).toContain('500');
  });

  it('shows the shop where each reward can be used', async () => {
    await load();
    const shops = [...page.querySelectorAll('.reward .shop')].map((shop) => shop.textContent);

    expect(shops[0]).toContain(`${ro.wallet.usableAt} Auchan`);
    expect(shops[1]).toContain(`${ro.wallet.usableAt} Carrefour`);
  });

  it('marks rewards as simulated', async () => {
    await load();

    expect(page.textContent).toContain(ro.wallet.simulated);
  });

  it('blocks rewards the client cannot afford, and shows the gap', async () => {
    await load();
    const [affordable, tooExpensive] = redeemButtons();

    expect(affordable.disabled).toBe(false);
    expect(tooExpensive.disabled).toBe(true);
    expect(tooExpensive.closest('.reward')!.querySelector('.short')!.textContent).toContain('3750');
  });

  it('puts the price on the button and the missing points under the name', async () => {
    await load();
    const [affordable, tooExpensive] = redeemButtons();
    const [affordableCard, tooExpensiveCard] = [affordable, tooExpensive].map((b) => b.closest('.reward')!);

    expect(affordable.textContent?.trim()).toBe(`500 ${ro.wallet.points}`);
    expect(tooExpensive.textContent?.trim()).toBe(`5000 ${ro.wallet.points}`);
    expect(affordableCard.querySelector('.short')).toBeNull();
    expect(tooExpensiveCard.querySelector('.short')!.textContent).toContain(`${ro.wallet.short} 3750`);
    expect(affordable.getAttribute('aria-label')).toContain(ro.wallet.redeem);
  });

  it('shows the history, newest as given, with signs and dates', async () => {
    await load();
    const entries = [...page.querySelectorAll('.entry')].map((entry) => entry.textContent);

    expect(entries[0]).toContain('+418');
    expect(entries[0]).toContain('Bon Auchan');
    expect(entries[0]).toContain('05.11.2026');
    expect(entries[1]).toContain('-500');
  });

  it('marks earned and spent points differently', async () => {
    await load();
    const entries = page.querySelectorAll('.entry');

    expect(entries[0].classList.contains('earned')).toBe(true);
    expect(entries[1].classList.contains('earned')).toBe(false);
  });

  it('explains an empty history', async () => {
    await load({ balance: 0, history: [] });

    expect(page.textContent).toContain(ro.wallet.noHistory);
  });

  it('opens the new voucher straight after redeeming', async () => {
    await redeemFirst();
    const view = page.querySelector('.voucher-view');

    expect(view?.textContent).toContain('Cafea');
    expect(view?.textContent).toContain('Auchan');
    expect(view?.textContent).toContain('DEMO-ABC123');
    expect(view?.textContent).toContain('06.12.2026');
  });

  it('draws a QR code on the voucher', async () => {
    await redeemFirst();

    const path = page.querySelector('.voucher-view svg path');
    expect(path?.getAttribute('d')).toMatch(/^M/);
    expect(page.querySelector('.voucher-view svg')?.getAttribute('aria-label')).toContain(
      'DEMO-ABC123',
    );
  });

  it('labels the voucher as a demo', async () => {
    await redeemFirst();

    expect(page.querySelector('.voucher-view')?.textContent).toContain(ro.wallet.voucherDemo);
  });

  it('updates the balance after redeeming', async () => {
    await redeemFirst();

    expect(page.querySelector('.balance')?.textContent).toContain('750');
  });

  it('keeps the voucher in the list after closing it', async () => {
    await redeemFirst();

    page.querySelector<HTMLButtonElement>('.close-voucher')!.click();
    await settle();

    expect(page.querySelector('.voucher-view')).toBeNull();
    expect(page.querySelector('.voucher')?.textContent).toContain('Cafea');
  });

  it('shows saved vouchers and opens one again', async () => {
    await load(wallet, [voucher]);

    page.querySelector<HTMLButtonElement>('.voucher')!.click();
    await settle();

    expect(page.querySelector('.voucher-view')?.textContent).toContain('DEMO-ABC123');
  });

  it('explains an empty voucher list', async () => {
    await load();

    expect(page.textContent).toContain(ro.wallet.noVouchers);
  });

  it('keeps the voucher if the balance fails to refresh', async () => {
    await load();

    redeemButtons()[0].click();
    http.expectOne('/api/rewards/1/redeem').flush(voucher);
    http.expectOne('/api/wallet').flush(null, { status: 500, statusText: 'Server Error' });
    await settle();

    expect(page.querySelector('.voucher-view')?.textContent).toContain('DEMO-ABC123');
    expect(page.textContent).not.toContain(ro.wallet.redeemFailed);
  });

  it('sends one request for a double tap', async () => {
    await load();
    const [reward] = redeemButtons();

    reward.click();
    await settle();
    expect(reward.disabled).toBe(true);
    reward.click();

    http.expectOne('/api/rewards/1/redeem').flush(voucher);
    http.expectOne('/api/wallet').flush(wallet);
  });

  it('explains when the points ran out meanwhile', async () => {
    await load();

    redeemButtons()[0].click();
    http
      .expectOne('/api/rewards/1/redeem')
      .flush(null, { status: 409, statusText: 'Conflict' });
    await settle();

    expect(page.textContent).toContain(ro.wallet.notEnough);
    expect(redeemButtons()[0].disabled).toBe(false);
  });

  it('explains any other redeem failure', async () => {
    await load();

    redeemButtons()[0].click();
    http
      .expectOne('/api/rewards/1/redeem')
      .flush(null, { status: 500, statusText: 'Server Error' });
    await settle();

    expect(page.textContent).toContain(ro.wallet.redeemFailed);
  });

  it('explains when the page fails to load', async () => {
    http.expectOne('/api/wallet').flush(null, { status: 500, statusText: 'Server Error' });
    http.match('/api/rewards');
    http.match('/api/vouchers');
    await settle();

    expect(page.textContent).toContain(ro.wallet.loadFailed);
    expect(page.textContent).not.toContain(ro.loading);
  });
});
