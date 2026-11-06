import { signal } from '@angular/core';

export type Language = 'ro' | 'en';

// Each name is written in its own language, so it can be found in either one.
export const LANGUAGES: { code: Language; name: string }[] = [
  { code: 'ro', name: 'Română' },
  { code: 'en', name: 'English' },
];

const LANGUAGE_KEY = 'dealdirection.language';

export function readSavedLanguage(): Language {
  return localStorage.getItem(LANGUAGE_KEY) === 'en' ? 'en' : 'ro';
}

export const language = signal<Language>(readSavedLanguage());
document.documentElement.lang = language();

export function setLanguage(code: Language): void {
  language.set(code);
  localStorage.setItem(LANGUAGE_KEY, code);
  document.documentElement.lang = code;
}
