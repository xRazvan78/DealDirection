import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { mockInterceptor } from './mock.interceptor';

describe('mockInterceptor login fallback', () => {
  let client: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([mockInterceptor])), provideHttpClientTesting()],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function demoLogin(): Promise<{ token: string }> {
    return firstValueFrom(client.post<{ token: string }>('/api/auth/demo', null));
  }

  it('uses the real backend when it answers', async () => {
    const login = demoLogin();

    http.expectOne('/api/auth/demo').flush({ token: 'real-token' });

    expect((await login).token).toBe('real-token');
  });

  it('falls back to a demo token when the backend is off', async () => {
    const login = demoLogin();

    http
      .expectOne('/api/auth/demo')
      .flush(null, { status: 500, statusText: 'Internal Server Error' });

    expect((await login).token).toBe('mock-token');
  });

  it('falls back when the backend cannot be reached at all', async () => {
    const login = demoLogin();

    http.expectOne('/api/auth/demo').error(new ProgressEvent('error'), { status: 0 });

    expect((await login).token).toBe('mock-token');
  });

  it('keeps real login rejections', async () => {
    const login = firstValueFrom(client.post('/api/auth/login', {}));

    http.expectOne('/api/auth/login').flush(null, { status: 401, statusText: 'Unauthorized' });

    await expect(login).rejects.toMatchObject({ status: 401 });
  });

  it('never touches other failing routes', async () => {
    const request = firstValueFrom(client.get('/api/lists'));

    http.expectOne('/api/lists').flush(null, { status: 500, statusText: 'Error' });

    await expect(request).rejects.toMatchObject({ status: 500 });
  });
});
