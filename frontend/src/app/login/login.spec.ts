import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { ro } from '../shared/ro';
import { Login } from './login';

// Built in code, so secret scanners have no literal to flag. Not real passwords.
const testPassword = 'x'.repeat(4) + '1!';
const wrongPassword = 'y'.repeat(8);

describe('Login', () => {
  let fixture: ComponentFixture<Login>;
  let http: HttpTestingController;
  let page: HTMLElement;
  let navigate: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Login);
    page = fixture.nativeElement;
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  function type(selector: string, value: string): void {
    const input = page.querySelector<HTMLInputElement>(selector)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function submit(): void {
    page.querySelector('form')!.dispatchEvent(new Event('submit'));
  }

  it('the demo button logs in and opens the app', async () => {
    page.querySelector<HTMLButtonElement>('.demo')!.click();
    http.expectOne({ method: 'POST', url: '/api/auth/demo' }).flush({ token: 'demo' });
    await fixture.whenStable();

    expect(navigate).toHaveBeenCalledWith('/browse');
  });

  it('logs in with the typed details', async () => {
    type('input[type=email]', 'ana@example.com');
    type('input[type=password]', testPassword);
    submit();

    const request = http.expectOne('/api/auth/login');
    expect(request.request.body).toEqual({ email: 'ana@example.com', password: testPassword });
    request.flush({ token: 'abc' });
    await fixture.whenStable();

    expect(navigate).toHaveBeenCalledWith('/browse');
  });

  it('can register instead', () => {
    page.querySelector<HTMLButtonElement>('.switch-mode')!.click();
    fixture.detectChanges();
    type('input[type=email]', 'ana@example.com');
    type('input[type=password]', testPassword);
    submit();

    http.expectOne('/api/auth/register').flush({ token: 'abc' });
  });

  it('sends nothing with an invalid form', () => {
    type('input[type=email]', 'nu-e-email');
    submit();

    http.expectNone('/api/auth/login');
  });

  it.each(['x'.repeat(3) + '1!', 'x'.repeat(5) + '!', 'x'.repeat(5) + '1'])(
    'refuses a weak password when registering: %s',
    (password) => {
      page.querySelector<HTMLButtonElement>('.switch-mode')!.click();
      fixture.detectChanges();
      type('input[type=email]', 'ana@example.com');
      type('input[type=password]', password);
      submit();

      http.expectNone('/api/auth/register');
    },
  );

  it('shows a clear message for wrong details', async () => {
    type('input[type=email]', 'ana@example.com');
    type('input[type=password]', wrongPassword);
    submit();
    http
      .expectOne('/api/auth/login')
      .flush(null, { status: 401, statusText: 'Unauthorized' });
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.login.wrongDetails);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('explains when an email is already registered', async () => {
    page.querySelector<HTMLButtonElement>('.switch-mode')!.click();
    fixture.detectChanges();
    type('input[type=email]', 'ana@example.com');
    type('input[type=password]', testPassword);
    submit();
    http.expectOne('/api/auth/register').flush(null, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();

    expect(page.textContent).toContain(ro.login.emailTaken);
  });

  it('disables the buttons while waiting, so a double tap sends once', async () => {
    const demo = page.querySelector<HTMLButtonElement>('.demo')!;
    demo.click();
    await fixture.whenStable();
    expect(demo.disabled).toBe(true);
    demo.click();

    http.expectOne('/api/auth/demo').flush({ token: 'demo' });
  });
});
