import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Store } from '../core/models';
import { ro } from '../shared/ro';
import { Settings } from './settings';

const stores: Store[] = [
  { id: 1, name: 'Auchan', colour: '#e2001a', logo: null, selected: true },
  { id: 2, name: 'Carrefour', colour: '#004e9f', logo: null, selected: false },
];

describe('Settings', () => {
  let fixture: ComponentFixture<Settings>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('dealdirection.token', 'abc');
    await TestBed.configureTestingModule({
      imports: [Settings],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Settings);
    page = fixture.nativeElement;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  async function loadStores(): Promise<void> {
    http.expectOne('/api/stores').flush(stores);
    await fixture.whenStable();
  }

  function toggles(): HTMLInputElement[] {
    return [...page.querySelectorAll<HTMLInputElement>('input[type=checkbox]')];
  }

  it('shows a loading message first', () => {
    expect(page.textContent).toContain(ro.loading);
    http.expectOne('/api/stores').flush(stores);
  });

  it('shows each store with its current selection', async () => {
    await loadStores();

    expect(page.textContent).toContain('Auchan');
    expect(page.textContent).toContain('Carrefour');
    expect(toggles().map((toggle) => toggle.checked)).toEqual([true, false]);
  });

  it('saves the new selection when a toggle changes', async () => {
    await loadStores();

    toggles()[1].click();

    const request = http.expectOne({ method: 'PUT', url: '/api/me/stores' });
    expect(request.request.body).toEqual({ store_ids: [1, 2] });
    request.flush(null);
  });

  it('undoes the toggle and explains when saving fails', async () => {
    await loadStores();

    toggles()[1].click();
    http.expectOne('/api/me/stores').flush(null, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();

    expect(toggles()[1].checked).toBe(false);
    expect(page.textContent).toContain(ro.settings.saveFailed);
  });

  it('shows a message when stores fail to load', async () => {
    http.expectOne('/api/stores').flush(null, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.settings.loadFailed);
  });

  it('logs out and opens the login page', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    await loadStores();

    page.querySelector<HTMLButtonElement>('.logout')!.click();

    expect(localStorage.getItem('dealdirection.token')).toBeNull();
    expect(navigate).toHaveBeenCalledWith('/login');
  });
});
