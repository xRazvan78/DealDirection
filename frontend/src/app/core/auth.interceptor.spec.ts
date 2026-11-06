import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { AuthService } from './auth';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('dealdirection.token', 'abc');
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  it('sends the token on API calls', () => {
    client.get('/api/wallet').subscribe();

    const request = http.expectOne('/api/wallet');
    expect(request.request.headers.get('Authorization')).toBe('Bearer abc');
    request.flush({});
  });

  it('keeps the token off other addresses', () => {
    client.get('https://example.com/data').subscribe();

    const request = http.expectOne('https://example.com/data');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({});
  });

  it('sends nothing when logged out', () => {
    auth.logout();
    client.get('/api/wallet').subscribe();

    const request = http.expectOne('/api/wallet');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({});
  });

  it('logs out and redirects on a 401', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    let status = 0;

    client.get('/api/wallet').subscribe({ error: (error) => (status = error.status) });
    http.expectOne('/api/wallet').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(auth.token()).toBeNull();
    expect(navigate).toHaveBeenCalledWith('/login');
    expect(status).toBe(401);
  });

  it('leaves other errors alone', () => {
    client.get('/api/wallet').subscribe({ error: () => undefined });
    http.expectOne('/api/wallet').flush(null, { status: 500, statusText: 'Server Error' });

    expect(auth.token()).toBe('abc');
  });
});
