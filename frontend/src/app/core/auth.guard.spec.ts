import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { authGuard } from './auth.guard';

@Component({ template: '' })
class Blank {}

describe('authGuard', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          { path: 'login', component: Blank },
          { path: 'wallet', component: Blank, canActivate: [authGuard] },
        ]),
      ],
    });
  });

  it('redirects to login without a token', async () => {
    const harness = await RouterTestingHarness.create();

    await harness.navigateByUrl('/wallet');

    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('allows the page with a token', async () => {
    localStorage.setItem('dealdirection.token', 'abc');
    const harness = await RouterTestingHarness.create();

    await harness.navigateByUrl('/wallet');

    expect(TestBed.inject(Router).url).toBe('/wallet');
  });
});
