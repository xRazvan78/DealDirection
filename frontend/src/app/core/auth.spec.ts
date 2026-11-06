import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth';

describe('AuthService', () => {
  let http: HttpTestingController;

  function setup(): AuthService {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    return TestBed.inject(AuthService);
  }

  beforeEach(() => localStorage.clear());
  afterEach(() => http.verify());

  it('stores the token after login', () => {
    const auth = setup();

    auth.login({ email: 'ana@example.com', password: 'parola123' }).subscribe();
    const request = http.expectOne('/api/auth/login');
    request.flush({ token: 'abc' });

    expect(request.request.body).toEqual({ email: 'ana@example.com', password: 'parola123' });
    expect(auth.token()).toBe('abc');
    expect(localStorage.getItem('dealdirection.token')).toBe('abc');
  });

  it('stores the token after registering', () => {
    const auth = setup();

    auth.register({ email: 'ana@example.com', password: 'parola123' }).subscribe();
    http.expectOne('/api/auth/register').flush({ token: 'new' });

    expect(auth.token()).toBe('new');
  });

  it('calls the demo route', () => {
    const auth = setup();

    auth.demo().subscribe();
    http.expectOne({ method: 'POST', url: '/api/auth/demo' }).flush({ token: 'demo' });

    expect(auth.token()).toBe('demo');
  });

  it('restores a saved token', () => {
    localStorage.setItem('dealdirection.token', 'saved');

    expect(setup().token()).toBe('saved');
  });

  it('clears the token on logout', () => {
    localStorage.setItem('dealdirection.token', 'saved');
    const auth = setup();

    auth.logout();

    expect(auth.token()).toBeNull();
    expect(localStorage.getItem('dealdirection.token')).toBeNull();
  });
});
