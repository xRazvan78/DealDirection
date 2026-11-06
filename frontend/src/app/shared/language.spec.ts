import { en } from './en';
import { language, readSavedLanguage, setLanguage } from './language';
import { ro, romanian } from './ro';

function keysOf(text: object, prefix = ''): string[] {
  return Object.entries(text).flatMap(([key, value]) =>
    typeof value === 'object' ? keysOf(value as object, `${prefix}${key}.`) : `${prefix}${key}`,
  );
}

function valuesOf(text: object): string[] {
  return Object.values(text).flatMap((value) =>
    typeof value === 'object' ? valuesOf(value as object) : (value as string),
  );
}

describe('language', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    setLanguage('ro');
    localStorage.clear();
  });

  it('starts in Romanian', () => {
    expect(readSavedLanguage()).toBe('ro');
    expect(ro.nav.home).toBe('Acasă');
  });

  it('switches every text to English', () => {
    setLanguage('en');

    expect(ro.nav.home).toBe('Home');
    expect(ro.cart.saveList).toBe('Save list');
  });

  it('switches back to Romanian', () => {
    setLanguage('en');

    setLanguage('ro');

    expect(ro.nav.home).toBe('Acasă');
  });

  it('remembers the choice', () => {
    setLanguage('en');

    expect(readSavedLanguage()).toBe('en');
  });

  it('ignores an unknown saved language', () => {
    localStorage.setItem('dealdirection.language', 'fr');

    expect(readSavedLanguage()).toBe('ro');
  });

  it('marks the page language, for browsers and screen readers', () => {
    setLanguage('en');

    expect(document.documentElement.lang).toBe('en');
    expect(language()).toBe('en');
  });

  it('has every text in both languages', () => {
    expect(keysOf(en).sort()).toEqual(keysOf(romanian).sort());
  });

  it('leaves no text empty', () => {
    expect(valuesOf(en).filter((text) => !text.trim())).toEqual([]);
    expect(valuesOf(romanian).filter((text) => !text.trim())).toEqual([]);
  });

  it('really translates the sentences', () => {
    const same = keysOf(en).filter((key) => {
      const read = (text: object): unknown =>
        key.split('.').reduce<unknown>((part, name) => (part as Record<string, unknown>)[name], text);
      return read(en) === read(romanian);
    });

    // Names and words that are the same in both languages.
    expect(same.sort()).toEqual(
      [
        'appName',
        'browse.pointShop',
        'cart.pdf',
        'cart.total',
        'login.email',
        'nav.wallet',
        'wallet.title',
      ].sort(),
    );
  });
});
