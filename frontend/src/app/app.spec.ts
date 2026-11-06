import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { App } from './app';
import { setLanguage } from './shared/language';
import { CartService } from './cart/cart.service';
import { ro } from './shared/ro';

@Component({ template: '' })
class Blank {}

describe('App', () => {
  let fixture: ComponentFixture<App>;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([
          { path: 'login', component: Blank },
          { path: 'browse', component: Blank },
          { path: 'lists', component: Blank },
          { path: 'cart', component: Blank },
        ]),
      ],
    }).compileComponents();
  });

  async function openAt(url: string): Promise<HTMLElement> {
    fixture = TestBed.createComponent(App);
    await TestBed.inject(Router).navigateByUrl(url);
    await fixture.whenStable();
    return fixture.nativeElement;
  }

  async function openMenu(page: HTMLElement): Promise<void> {
    page.querySelector<HTMLButtonElement>('.menu-button')!.click();
    await fixture.whenStable();
  }

  function scroll(page: HTMLElement, top: number): HTMLElement {
    const content = page.querySelector<HTMLElement>('.content')!;
    content.scrollTop = top;
    content.dispatchEvent(new Event('scroll'));
    return content;
  }

  it('hides the scroll-to-top button near the top', async () => {
    const page = await openAt('/browse');

    scroll(page, 100);
    await fixture.whenStable();

    expect(page.querySelector('.scroll-top')).toBeNull();
  });

  it('shows the scroll-to-top button after scrolling down', async () => {
    const page = await openAt('/browse');

    scroll(page, 400);
    await fixture.whenStable();

    expect(page.querySelector('.scroll-top')?.getAttribute('aria-label')).toBe(ro.nav.scrollTop);
  });

  it('scrolls back to the top when pressed', async () => {
    const page = await openAt('/browse');
    const content = scroll(page, 400);
    content.scrollTo = vi.fn();
    await fixture.whenStable();

    page.querySelector<HTMLButtonElement>('.scroll-top')!.click();

    expect(content.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });

  it('hides the button again after scrolling back up', async () => {
    const page = await openAt('/browse');
    scroll(page, 400);
    await fixture.whenStable();

    scroll(page, 0);
    await fixture.whenStable();

    expect(page.querySelector('.scroll-top')).toBeNull();
  });

  it('never shows the button on the cart, where it would cover Scan receipt', async () => {
    const page = await openAt('/cart');

    scroll(page, 400);
    await fixture.whenStable();

    expect(page.querySelector('.scroll-top')).toBeNull();
  });

  it('hides the button when opening another page', async () => {
    const page = await openAt('/browse');
    scroll(page, 400);
    await fixture.whenStable();

    await TestBed.inject(Router).navigateByUrl('/lists');
    await fixture.whenStable();

    expect(page.querySelector('.scroll-top')).toBeNull();
  });

  it('shows three tabs: home, cart, cards, from left to right', async () => {
    const page = await openAt('/browse');
    const tabs = [...page.querySelectorAll('.bottom-nav a')];

    expect(tabs.map((tab) => tab.getAttribute('href'))).toEqual(['/browse', '/cart', '/cards']);
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual([
      ro.nav.home,
      ro.nav.cart,
      ro.nav.cards,
    ]);
  });

  it('translates the tabs and menu when the language changes', async () => {
    const page = await openAt('/browse');
    await openMenu(page);

    setLanguage('en');
    await fixture.whenStable();
    const tabs = [...page.querySelectorAll('.bottom-nav a')].map((a) => a.textContent?.trim());
    const menu = [...page.querySelectorAll('.side-menu a')].map((a) => a.textContent?.trim());
    setLanguage('ro');

    expect(tabs).toEqual(['Home', 'Cart', 'Cards']);
    expect(menu).toEqual(['Lists', 'Point Shop', 'Settings']);
  it('shows no count on the cart tab while the cart is empty', async () => {
    const page = await openAt('/browse');

    expect(page.querySelector('.cart-count')).toBeNull();
  });

  it('counts every unit in the cart, not the distinct products', async () => {
    const cart = TestBed.inject(CartService);
    cart.add({ name: 'Apă minerală', quantity: '5', price: '3' });
    cart.add({ name: 'Apă plată', quantity: '3', price: '2' });

    const page = await openAt('/browse');
    const count = page.querySelector('.cart-count');

    expect(count?.textContent).toBe('8');
    expect(count?.closest('a')?.getAttribute('href')).toBe('/cart');
  });

  it('removes the count once the cart is emptied', async () => {
    const cart = TestBed.inject(CartService);
    cart.add({ name: 'Mere', quantity: '2', price: '3' });
    const page = await openAt('/browse');

    cart.clear();
    await fixture.whenStable();

    expect(page.querySelector('.cart-count')).toBeNull();
  });

  it('has the hamburger on the left and the account link on the right', async () => {
    const page = await openAt('/browse');
    const bar = page.querySelector('.top-bar')!;

    expect(bar.firstElementChild?.classList.contains('menu-button')).toBe(true);
    expect(bar.lastElementChild?.getAttribute('href')).toBe('/settings');
    expect(bar.lastElementChild?.getAttribute('aria-label')).toBe(ro.nav.account);
  });

  it('keeps the menu closed at first', async () => {
    const page = await openAt('/browse');

    expect(page.querySelector('.side-menu')).toBeNull();
    expect(page.querySelector('.menu-button')?.getAttribute('aria-expanded')).toBe('false');
  });

  it('opens the menu with lists, Point Shop and settings', async () => {
    const page = await openAt('/browse');

    await openMenu(page);
    const links = [...page.querySelectorAll('.side-menu a')].map((a) => a.getAttribute('href'));

    expect(links).toEqual(['/lists', '/wallet', '/settings']);
    expect(page.querySelector('.menu-button')?.getAttribute('aria-expanded')).toBe('true');
  });

  it('closes the menu after choosing a link', async () => {
    const page = await openAt('/browse');
    await openMenu(page);

    page.querySelector<HTMLAnchorElement>('.side-menu a')!.click();
    await fixture.whenStable();

    expect(page.querySelector('.side-menu')).toBeNull();
    expect(TestBed.inject(Router).url).toBe('/lists');
  });

  it('closes the menu when tapping outside it', async () => {
    const page = await openAt('/browse');
    await openMenu(page);

    page.querySelector<HTMLElement>('.menu-backdrop')!.click();
    await fixture.whenStable();

    expect(page.querySelector('.side-menu')).toBeNull();
  });

  it('hides the navigation on the login page', async () => {
    const page = await openAt('/login');

    expect(page.querySelector('.bottom-nav')).toBeNull();
    expect(page.querySelector('.top-bar')).toBeNull();
  });
});
