import { TestBed } from '@angular/core/testing';
import { CardsService } from './cards.service';

const image = 'data:image/jpeg;base64,AAAA';

describe('CardsService', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  function create(): CardsService {
    return TestBed.inject(CardsService);
  }

  it('saves a card with its label and image', () => {
    const cards = create();

    expect(cards.add('Auchan', image)).toBe(true);

    expect(cards.cards()[0]).toMatchObject({ label: 'Auchan', image });
  });

  it('gives every card its own id', () => {
    const cards = create();

    cards.add('Auchan', image);
    cards.add('Lidl', image);

    expect(new Set(cards.cards().map(({ id }) => id)).size).toBe(2);
  });

  it('keeps cards after a reload', () => {
    create().add('Auchan', image);
    TestBed.resetTestingModule();

    expect(create().cards()[0].label).toBe('Auchan');
  });

  it('survives damaged saved data', () => {
    localStorage.setItem('dealdirection.cards', '{broken');

    expect(create().cards()).toEqual([]);
  });

  it('removes one card', () => {
    const cards = create();
    cards.add('Auchan', image);
    cards.add('Lidl', image);

    cards.remove(cards.cards()[0].id);

    expect(cards.cards().map(({ label }) => label)).toEqual(['Lidl']);
  });

  it('refuses a card when the device has no room, and keeps the others', () => {
    const cards = create();
    cards.add('Auchan', image);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Full', 'QuotaExceededError');
    });

    expect(cards.add('Lidl', image)).toBe(false);

    expect(cards.cards().map(({ label }) => label)).toEqual(['Auchan']);
  });

  it('clears everything', () => {
    const cards = create();
    cards.add('Auchan', image);

    cards.clear();

    expect(cards.cards()).toEqual([]);
    expect(localStorage.getItem('dealdirection.cards')).toBeNull();
  });
});
