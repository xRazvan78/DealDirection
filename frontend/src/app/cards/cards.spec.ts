import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ro } from '../shared/ro';
import { CardImageReader } from './card-image';
import { Cards } from './cards';
import { CardsService } from './cards.service';

const image = 'data:image/jpeg;base64,AAAA';
const photo = new File(['x'], 'card.jpg', { type: 'image/jpeg' });

describe('Cards', () => {
  let fixture: ComponentFixture<Cards>;
  let page: HTMLElement;
  let cards: CardsService;
  let read: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({ imports: [Cards] }).compileComponents();
    cards = TestBed.inject(CardsService);
    read = vi.spyOn(TestBed.inject(CardImageReader), 'read').mockResolvedValue(image);
  });

  afterEach(() => vi.restoreAllMocks());

  async function open(): Promise<void> {
    fixture = TestBed.createComponent(Cards);
    page = fixture.nativeElement;
    await fixture.whenStable();
  }

  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    await fixture.whenStable();
  }

  function button(selector: string): HTMLButtonElement {
    return page.querySelector<HTMLButtonElement>(selector)!;
  }

  async function press(selector: string): Promise<void> {
    button(selector).click();
    await settle();
  }

  async function pick(selector: string, file: File): Promise<void> {
    const input = page.querySelector<HTMLInputElement>(selector)!;
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await settle();
  }

  async function label(text: string): Promise<void> {
    const input = page.querySelector<HTMLInputElement>('.card-label')!;
    input.value = text;
    input.dispatchEvent(new Event('input'));
    await settle();
  }

  async function submit(): Promise<void> {
    page.querySelector('.new-card')!.dispatchEvent(new Event('submit'));
    await settle();
  }

  it('explains an empty wallet', async () => {
    await open();

    expect(page.textContent).toContain(ro.cards.empty);
  });

  it('shows each saved card with its label', async () => {
    cards.add('Auchan', image);
    cards.add('Lidl', image);
    await open();

    const labels = [...page.querySelectorAll('.card .name')].map((name) => name.textContent);
    expect(labels).toEqual(['Auchan', 'Lidl']);
  });

  it('keeps + after the last card', async () => {
    cards.add('Auchan', image);
    await open();

    const order = [...page.querySelector('.list')!.children].map((child) => child.className);
    expect(order.at(-1)).toContain('add-card');
  });

  it('offers the two ways to add a card when + is pressed', async () => {
    await open();
    expect(page.querySelector('.add-options')).toBeNull();

    await press('.add-card');

    expect(button('.pick-photo').textContent).toContain(ro.cards.choosePhoto);
    expect(button('.scan-card').textContent).toContain(ro.cards.scanCard);
  });

  it('can close the options', async () => {
    await open();
    await press('.add-card');

    await press('.close-options');

    expect(page.querySelector('.add-options')).toBeNull();
  });

  it('chooses an existing photo without forcing the camera', async () => {
    await open();

    const input = page.querySelector('.photo-input');
    expect(input?.getAttribute('accept')).toBe('image/*');
    expect(input?.hasAttribute('capture')).toBe(false);
  });

  it('opens the camera to scan a physical card', async () => {
    await open();

    expect(page.querySelector('.camera-input')?.getAttribute('capture')).toBe('environment');
  });

  it('shows the photo and asks for a label', async () => {
    await open();

    await pick('.photo-input', photo);

    expect(read).toHaveBeenCalledWith(photo);
    expect(page.querySelector('.new-card img')?.getAttribute('src')).toBe(image);
    expect(page.querySelector('.card-label')).not.toBeNull();
  });

  it('never fills in the label or lets the browser suggest one', async () => {
    await open();

    await pick('.camera-input', photo);
    const input = page.querySelector<HTMLInputElement>('.card-label');

    expect(input?.value).toBe('');
    expect(input?.getAttribute('autocomplete')).toBe('off');
  });

  it('saves the card with the typed label', async () => {
    await open();
    await pick('.camera-input', photo);

    await label('  Card Auchan  ');
    await submit();

    expect(cards.cards()[0]).toMatchObject({ label: 'Card Auchan', image });
    expect(page.querySelector('.new-card')).toBeNull();
  });

  it('requires a label', async () => {
    await open();
    await pick('.photo-input', photo);

    await submit();

    expect(page.textContent).toContain(ro.cards.labelRequired);
    expect(cards.cards()).toEqual([]);
  });

  it('can cancel a new card', async () => {
    await open();
    await pick('.photo-input', photo);

    await press('.cancel-card');

    expect(page.querySelector('.new-card')).toBeNull();
    expect(cards.cards()).toEqual([]);
  });

  it('rejects a file that is not an image', async () => {
    await open();

    await pick('.photo-input', new File(['x'], 'card.pdf', { type: 'application/pdf' }));

    expect(read).not.toHaveBeenCalled();
    expect(page.textContent).toContain(ro.cards.wrongFile);
  });

  it('rejects a file that is too large', async () => {
    await open();
    const huge = new File(['x'], 'card.jpg', { type: 'image/jpeg' });
    Object.defineProperty(huge, 'size', { value: 11 * 1024 * 1024 });

    await pick('.photo-input', huge);

    expect(read).not.toHaveBeenCalled();
    expect(page.textContent).toContain(ro.cards.wrongFile);
  });

  it('explains a photo that could not be read', async () => {
    read.mockRejectedValue(new Error('bad'));
    await open();

    await pick('.photo-input', photo);

    expect(page.textContent).toContain(ro.cards.readFailed);
  });

  it('explains when the device has no room', async () => {
    vi.spyOn(cards, 'add').mockReturnValue(false);
    await open();
    await pick('.photo-input', photo);

    await label('Auchan');
    await submit();

    expect(page.textContent).toContain(ro.cards.noRoom);
    expect(page.querySelector('.new-card')).not.toBeNull();
  });

  describe('viewing a card', () => {
    beforeEach(async () => {
      cards.add('Auchan', image);
      await open();
      await press('.card');
    });

    it('shows the code large', () => {
      expect(page.querySelector('.card-view h2')?.textContent).toContain('Auchan');
      expect(page.querySelector('.card-view img')?.getAttribute('src')).toBe(image);
    });

    it('closes again', async () => {
      await press('.close-view');

      expect(page.querySelector('.card-view')).toBeNull();
    });

    it('asks before deleting', async () => {
      await press('.delete-card');

      expect(cards.cards().length).toBe(1);
      expect(page.textContent).toContain(ro.cards.confirmDelete);
    });

    it('deletes after confirming', async () => {
      await press('.delete-card');
      await press('.confirm-delete');

      expect(cards.cards()).toEqual([]);
      expect(page.querySelector('.card-view')).toBeNull();
    });

    it('keeps the card if the delete is called off', async () => {
      await press('.delete-card');
      await press('.keep-card');

      expect(cards.cards().length).toBe(1);
      expect(page.querySelector('.delete-card')).not.toBeNull();
    });

    it('does not ask again on the next card after a delete', async () => {
      cards.add('Lidl', image);
      await settle();
      await press('.delete-card');
      await press('.confirm-delete');

      await press('.card');

      expect(page.querySelector('.card-view h2')?.textContent).toContain('Lidl');
      expect(page.querySelector('.confirm-delete')).toBeNull();
    });
  });
});
