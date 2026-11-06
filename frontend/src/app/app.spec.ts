import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { App } from './app';
import { ro } from './shared/ro';

@Component({ template: '' })
class Blank {}

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([
          { path: 'login', component: Blank },
          { path: 'browse', component: Blank },
        ]),
      ],
    }).compileComponents();
  });

  async function openAt(url: string): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(Router).navigateByUrl(url);
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  it('shows three tabs: deals, cart, cards, from left to right', async () => {
    const page = await openAt('/browse');
    const tabs = [...page.querySelectorAll('.bottom-nav a')];

    expect(tabs.map((tab) => tab.getAttribute('href'))).toEqual(['/browse', '/cart', '/cards']);
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual([
      ro.nav.deals,
      ro.nav.cart,
      ro.nav.cards,
    ]);
  });

  it('keeps lists, points and settings reachable from the top bar', async () => {
    const page = await openAt('/browse');
    const links = [...page.querySelectorAll('.top-bar a')].map((a) => a.getAttribute('href'));

    expect(links).toEqual(['/lists', '/wallet', '/settings']);
  });

  it('hides the navigation on the login page', async () => {
    const page = await openAt('/login');

    expect(page.querySelector('.bottom-nav')).toBeNull();
    expect(page.querySelector('.top-bar')).toBeNull();
  });
});
