import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { ImportPreview, SearchResult } from '../core/models';
import { ro } from '../shared/ro';
import { Import } from './import';

const preview: ImportPreview = {
  items: [
    { food: 'piept de pui', size_category_id: 100, path: 'Carne de pui > Piept > 1 kg', packs: 2 },
    { food: 'lapte', size_category_id: 200, path: 'Lapte > 3.5% > 1 l', packs: 1 },
  ],
  unmapped: ['quinoa', 'tofu'],
};
const results: SearchResult[] = [
  { size_category_id: 300, path: 'Leguminoase > Linte și năut > 500 g', generic: null },
];
const serverError = { status: 500, statusText: 'Server Error' };
const photo = new File(['poza'], 'lista.png', { type: 'image/png' });

describe('Import', () => {
  let fixture: ComponentFixture<Import>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Import],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Import);
    page = fixture.nativeElement;
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  function fileInput(): HTMLInputElement {
    return page.querySelector<HTMLInputElement>('input[type="file"]')!;
  }

  function textBox(): HTMLTextAreaElement {
    return page.querySelector<HTMLTextAreaElement>('textarea')!;
  }

  function submitButton(): HTMLButtonElement {
    return page.querySelector<HTMLButtonElement>('.submit')!;
  }

  function confirmButton(): HTMLButtonElement {
    return page.querySelector<HTMLButtonElement>('.confirm')!;
  }

  async function chooseFile(file: File | null): Promise<void> {
    Object.defineProperty(fileInput(), 'files', { value: file ? [file] : [], configurable: true });
    fileInput().dispatchEvent(new Event('change'));
    await fixture.whenStable();
  }

  async function typeText(text: string): Promise<void> {
    textBox().value = text;
    textBox().dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function setDays(days: string): Promise<void> {
    const input = page.querySelector<HTMLInputElement>('.days input')!;
    input.value = days;
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function submit(): Promise<TestRequest> {
    page.querySelector('form.source')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
    return http.expectOne('/api/imports');
  }

  function body(request: TestRequest): FormData {
    return request.request.body as FormData;
  }

  async function reachReview(reply: ImportPreview = preview): Promise<void> {
    await typeText('200g piept de pui zilnic');
    (await submit()).flush(reply);
    await fixture.whenStable();
  }

  function unmappedRow(index: number): HTMLElement {
    return page.querySelectorAll<HTMLElement>('.unmapped-row')[index];
  }

  async function removeUnmapped(): Promise<void> {
    while (page.querySelector('.unmapped-row')) {
      unmappedRow(0).querySelector<HTMLButtonElement>('.remove')!.click();
      await fixture.whenStable();
    }
  }

  async function searchFor(food: number, query: string): Promise<void> {
    unmappedRow(food).querySelector<HTMLButtonElement>('.pick')!.click();
    await fixture.whenStable();
    const input = page.querySelector<HTMLInputElement>('.picker input')!;
    input.value = query;
    input.dispatchEvent(new Event('input'));
    page.querySelector('.picker')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
  }

  describe('choosing what to import', () => {
    it('accepts a PDF or a picture', () => {
      expect(fileInput().accept).toBe('application/pdf,image/*');
    });

    it('starts with the import button off', () => {
      expect(submitButton().disabled).toBe(true);
    });

    it('sends a file with the number of days', async () => {
      await chooseFile(photo);
      await setDays('14');

      const request = await submit();

      expect(body(request).get('file')).toBe(photo);
      expect(body(request).get('days')).toBe('14');
      expect(body(request).has('text')).toBe(false);
      request.flush(preview);
    });

    it('sends pasted text with the number of days', async () => {
      await typeText('  200g piept de pui zilnic  ');

      const request = await submit();

      expect(body(request).get('text')).toBe('200g piept de pui zilnic');
      expect(body(request).get('days')).toBe('7');
      expect(body(request).has('file')).toBe(false);
      request.flush(preview);
    });

    it('clears pasted text when a file is chosen', async () => {
      await typeText('lapte');

      await chooseFile(photo);

      expect(textBox().value).toBe('');
    });

    it('clears the file when text is typed', async () => {
      await chooseFile(photo);

      await typeText('lapte');
      const request = await submit();

      expect(body(request).has('file')).toBe(false);
      expect(fileInput().value).toBe('');
      request.flush(preview);
    });

    it.each(['0', '-3', '2.5', ''])('keeps the button off for %s days', async (days) => {
      await typeText('lapte');

      await setDays(days);

      expect(submitButton().disabled).toBe(true);
    });

    it('ignores spaces with no text', async () => {
      await typeText('   ');

      expect(submitButton().disabled).toBe(true);
    });
  });

  describe('while reading', () => {
    it('shows a progress message and blocks a second import', async () => {
      await typeText('lapte');

      const request = await submit();

      expect(page.textContent).toContain(ro.import.reading);
      expect(submitButton().disabled).toBe(true);
      request.flush(preview);
    });
  });

  describe('when reading fails', () => {
    async function failWith(status: number): Promise<void> {
      await typeText('lapte');
      (await submit()).flush(null, { status, statusText: 'Error' });
      await fixture.whenStable();
    }

    it('shows a retry message', async () => {
      await failWith(422);

      expect(page.querySelector('[role="alert"]')?.textContent).toContain(ro.import.failed);
    });

    it('explains a file that is too large', async () => {
      await failWith(413);

      expect(page.querySelector('[role="alert"]')?.textContent).toContain(ro.import.tooLarge);
    });

    it('explains a file of the wrong type', async () => {
      await failWith(415);

      expect(page.querySelector('[role="alert"]')?.textContent).toContain(ro.import.wrongType);
    });

    it('keeps the text so it can be tried again', async () => {
      await failWith(500);

      expect(textBox().value).toBe('lapte');
      expect(submitButton().disabled).toBe(false);

      (await submit()).flush(preview);
      await fixture.whenStable();
      expect(page.querySelector('[role="alert"]')).toBeNull();
    });
  });

  describe('reviewing the result', () => {
    it('shows each mapped item with its category and packs', async () => {
      await reachReview();
      const rows = page.querySelectorAll('.item-row');

      expect(rows.length).toBe(2);
      expect(rows[0].textContent).toContain('piept de pui');
      expect(rows[0].textContent).toContain('Carne de pui > Piept > 1 kg');
      expect(rows[0].textContent).toContain(`2 ${ro.import.packs}`);
    });

    it('uses the singular for one pack', async () => {
      await reachReview();

      expect(page.querySelectorAll('.item-row')[1].textContent).toContain(`1 ${ro.import.pack}`);
      expect(page.querySelectorAll('.item-row')[1].textContent).not.toContain(ro.import.packs);
    });

    it('flags foods it could not map', async () => {
      await reachReview();

      expect(page.textContent).toContain(ro.import.unmappedTitle);
      expect(unmappedRow(0).textContent).toContain('quinoa');
      expect(unmappedRow(1).textContent).toContain('tofu');
    });

    it('blocks confirming until every unmapped food is settled', async () => {
      await reachReview();

      expect(confirmButton().disabled).toBe(true);
    });

    it('removes an unmapped food', async () => {
      await reachReview();

      unmappedRow(0).querySelector<HTMLButtonElement>('.remove')!.click();
      await fixture.whenStable();

      expect(page.querySelectorAll('.unmapped-row').length).toBe(1);
      expect(page.textContent).not.toContain('quinoa');
    });

    it('allows confirming once unmapped foods are removed', async () => {
      await reachReview();

      await removeUnmapped();

      expect(confirmButton().disabled).toBe(false);
    });

    it('searches for a product for an unmapped food', async () => {
      await reachReview();

      await searchFor(0, 'quinoa');
      const request = http.expectOne((r) => r.url === '/api/search');
      expect(request.request.params.get('q')).toBe('quinoa');
      request.flush(results);
      await fixture.whenStable();

      expect(page.querySelector('.result')?.textContent).toContain(results[0].path);
    });

    it('starts the search from the food name', async () => {
      await reachReview();

      unmappedRow(1).querySelector<HTMLButtonElement>('.pick')!.click();
      await fixture.whenStable();

      expect(page.querySelector<HTMLInputElement>('.picker input')?.value).toBe('tofu');
    });

    it('moves a picked product into the list', async () => {
      await reachReview();
      await searchFor(0, 'quinoa');
      http.expectOne((r) => r.url === '/api/search').flush(results);
      await fixture.whenStable();

      page.querySelector<HTMLButtonElement>('.result')!.click();
      await fixture.whenStable();

      const rows = page.querySelectorAll('.item-row');
      expect(rows.length).toBe(3);
      expect(rows[2].textContent).toContain('quinoa');
      expect(rows[2].textContent).toContain(results[0].path);
      expect(page.querySelectorAll('.unmapped-row').length).toBe(1);
    });

    it('explains when a search finds nothing', async () => {
      await reachReview();
      await searchFor(0, 'xyz');

      http.expectOne((r) => r.url === '/api/search').flush([]);
      await fixture.whenStable();

      expect(page.textContent).toContain(ro.import.noResults);
    });

    it('explains when a search fails', async () => {
      await reachReview();
      await searchFor(0, 'quinoa');

      http.expectOne((r) => r.url === '/api/search').flush(null, serverError);
      await fixture.whenStable();

      expect(page.textContent).toContain(ro.import.searchFailed);
    });

    it('removes a mapped item', async () => {
      await reachReview();

      page.querySelector<HTMLButtonElement>('.item-row .remove')!.click();
      await fixture.whenStable();

      expect(page.querySelectorAll('.item-row').length).toBe(1);
    });

    it('blocks confirming an empty list', async () => {
      await reachReview({ items: [], unmapped: [] });

      expect(confirmButton().disabled).toBe(true);
      expect(page.textContent).toContain(ro.import.nothingLeft);
    });

    it('goes back to the start', async () => {
      await reachReview();

      page.querySelector<HTMLButtonElement>('.start-over')!.click();
      await fixture.whenStable();

      expect(fileInput()).not.toBeNull();
      expect(page.querySelector('.item-row')).toBeNull();
    });
  });

  describe('confirming', () => {
    async function confirmReview(): Promise<TestRequest> {
      confirmButton().click();
      await fixture.whenStable();
      return http.expectOne('/api/imports/confirm');
    }

    it('sends the list name and items, then opens the new list', async () => {
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
      await reachReview();
      await removeUnmapped();
      const name = page.querySelector<HTMLInputElement>('.list-name input')!;
      name.value = '  Plan alimentar  ';
      name.dispatchEvent(new Event('input'));
      await fixture.whenStable();

      const request = await confirmReview();
      expect(request.request.body).toEqual({
        name: 'Plan alimentar',
        items: [
          { size_category_id: 100, packs: 2 },
          { size_category_id: 200, packs: 1 },
        ],
      });
      request.flush({ list_id: 42 });
      await fixture.whenStable();

      expect(navigate).toHaveBeenCalledWith(['/cart', '42']);
    });

    it('suggests a list name', async () => {
      await reachReview();

      expect(page.querySelector<HTMLInputElement>('.list-name input')?.value).toBe(
        ro.import.defaultName,
      );
    });

    it('blocks confirming with no list name', async () => {
      await reachReview();
      await removeUnmapped();
      const name = page.querySelector<HTMLInputElement>('.list-name input')!;
      name.value = '   ';
      name.dispatchEvent(new Event('input'));
      await fixture.whenStable();

      expect(confirmButton().disabled).toBe(true);
    });

    it('sends a double tap once', async () => {
      vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
      await reachReview();
      await removeUnmapped();

      const request = await confirmReview();
      expect(confirmButton().disabled).toBe(true);

      request.flush({ list_id: 42 });
      await fixture.whenStable();
    });

    it('keeps the review when confirming fails', async () => {
      await reachReview();
      await removeUnmapped();

      (await confirmReview()).flush(null, serverError);
      await fixture.whenStable();

      expect(page.textContent).toContain(ro.import.confirmFailed);
      expect(page.querySelectorAll('.item-row').length).toBe(2);
      expect(confirmButton().disabled).toBe(false);
    });
  });
});
