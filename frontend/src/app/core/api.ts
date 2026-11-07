import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AuthResponse,
  CardBrand,
  CardScan,
  Category,
  CategoryProducts,
  Credentials,
  Directions,
  ImportConfirmation,
  ImportPreview,
  ListItem,
  ListPart,
  LoyaltyCard,
  NewListItem,
  PlanResult,
  ReceiptReading,
  ReceiptResult,
  Resolution,
  Reward,
  SearchResult,
  ShoppingList,
  Store,
  Voucher,
  Wallet,
} from './models';

// One typed method per backend route. Screens call this service, never HttpClient.
// Money arrives as strings: format it with formatLei and never use parseFloat.
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>('/api/health');
  }

  // Login
  register(details: Credentials): Observable<AuthResponse> {
    return this.http.post<AuthResponse>('/api/auth/register', details);
  }

  login(details: Credentials): Observable<AuthResponse> {
    return this.http.post<AuthResponse>('/api/auth/login', details);
  }

  demo(): Observable<AuthResponse> {
    return this.http.post<AuthResponse>('/api/auth/demo', null);
  }

  // Stores
  getStores(): Observable<Store[]> {
    return this.http.get<Store[]>('/api/stores');
  }

  setMyStores(storeIds: number[]): Observable<void> {
    return this.http.put<void>('/api/me/stores', { store_ids: storeIds });
  }

  getDirections(storeId: number, location?: { lat: number; lng: number }): Observable<Directions> {
    const params: Record<string, number> = location ? { ...location } : {};
    return this.http.get<Directions>(`/api/stores/${storeId}/directions`, { params });
  }

  // Catalog
  getCategories(parentId?: number): Observable<Category[]> {
    const params: Record<string, number> = parentId === undefined ? {} : { parent_id: parentId };
    return this.http.get<Category[]>('/api/categories', { params });
  }

  getCategoryProducts(categoryId: number, brand?: string): Observable<CategoryProducts> {
    const params: Record<string, string> = brand ? { brand_q: brand } : {};
    return this.http.get<CategoryProducts>(`/api/categories/${categoryId}/products`, { params });
  }

  search(query: string): Observable<SearchResult[]> {
    return this.http.get<SearchResult[]>('/api/search', {
      params: new HttpParams().set('q', query),
    });
  }

  // Lists
  createList(name: string): Observable<ShoppingList> {
    return this.http.post<ShoppingList>('/api/lists', { name });
  }

  getLists(): Observable<ShoppingList[]> {
    return this.http.get<ShoppingList[]>('/api/lists');
  }

  getList(listId: number): Observable<ShoppingList> {
    return this.http.get<ShoppingList>(`/api/lists/${listId}`);
  }

  renameList(listId: number, name: string): Observable<ShoppingList> {
    return this.http.patch<ShoppingList>(`/api/lists/${listId}`, { name });
  }

  deleteList(listId: number): Observable<void> {
    return this.http.delete<void>(`/api/lists/${listId}`);
  }

  completeList(listId: number): Observable<ShoppingList> {
    return this.http.post<ShoppingList>(`/api/lists/${listId}/complete`, null);
  }

  // List items
  addListItem(listId: number, item: NewListItem): Observable<ListItem> {
    return this.http.post<ListItem>(`/api/lists/${listId}/items`, item);
  }

  updateListItem(listId: number, itemId: number, quantity: string): Observable<ListItem> {
    return this.http.patch<ListItem>(`/api/lists/${listId}/items/${itemId}`, { quantity });
  }

  deleteListItem(listId: number, itemId: number): Observable<void> {
    return this.http.delete<void>(`/api/lists/${listId}/items/${itemId}`);
  }

  // Plans
  getPlans(listId: number, resolutions: Resolution[]): Observable<PlanResult> {
    return this.http.post<PlanResult>(`/api/lists/${listId}/plans`, { resolutions });
  }

  acceptSuggestion(listId: number): Observable<void> {
    return this.http.post<void>(`/api/lists/${listId}/suggestion/accept`, null);
  }

  activateList(
    listId: number,
    kind: 'single' | 'split',
    resolutions: Resolution[],
  ): Observable<void> {
    return this.http.post<void>(`/api/lists/${listId}/activate`, { kind, resolutions });
  }

  getListParts(listId: number): Observable<ListPart[]> {
    return this.http.get<ListPart[]>(`/api/lists/${listId}/parts`);
  }

  // Receipts
  uploadReceipt(listId: number, storeId: number, photo: File): Observable<ReceiptResult> {
    const body = new FormData();
    body.append('file', photo);
    return this.http.post<ReceiptResult>(`/api/lists/${listId}/receipts`, body, {
      params: { store_id: storeId },
    });
  }

  readReceipt(photo: File): Observable<ReceiptReading> {
    const body = new FormData();
    body.append('file', photo);
    return this.http.post<ReceiptReading>('/api/receipts/read', body);
  }

  // Import: send exactly one of `file` or `text`
  importList(days: number, source: { file: File } | { text: string }): Observable<ImportPreview> {
    const body = new FormData();
    body.append('days', String(days));
    if ('file' in source) {
      body.append('file', source.file);
    } else {
      body.append('text', source.text);
    }
    return this.http.post<ImportPreview>('/api/imports', body);
  }

  confirmImport(confirmation: ImportConfirmation): Observable<{ list_id: number }> {
    return this.http.post<{ list_id: number }>('/api/imports/confirm', confirmation);
  }

  // Wallet
  getWallet(): Observable<Wallet> {
    return this.http.get<Wallet>('/api/wallet');
  }

  getRewards(): Observable<Reward[]> {
    return this.http.get<Reward[]>('/api/rewards');
  }

  getVouchers(): Observable<Voucher[]> {
    return this.http.get<Voucher[]>('/api/vouchers');
  }

  redeemReward(rewardId: number): Observable<Voucher> {
    return this.http.post<Voucher>(`/api/rewards/${rewardId}/redeem`, null);
  }

  // Cards
  getCardBrands(): Observable<CardBrand[]> {
    return this.http.get<CardBrand[]>('/api/card-brands');
  }

  getCards(): Observable<LoyaltyCard[]> {
    return this.http.get<LoyaltyCard[]>('/api/cards');
  }

  // Reads the code from a card's photo and suggests its brand; saves nothing.
  scanCard(photo: File): Observable<CardScan> {
    const body = new FormData();
    body.append('file', photo);
    return this.http.post<CardScan>('/api/cards/scan', body);
  }

  // Saves a scanned code, or the photo itself when no code could be read.
  saveCard(brand: string, source: { scan: CardScan } | { photo: File }): Observable<LoyaltyCard> {
    const body = new FormData();
    body.append('brand', brand);
    if ('scan' in source) {
      body.append('code_text', source.scan.code_text);
      body.append('code_format', source.scan.code_format);
    } else {
      body.append('file', source.photo);
    }
    return this.http.post<LoyaltyCard>('/api/cards', body);
  }

  deleteCard(cardId: number): Observable<void> {
    return this.http.delete<void>(`/api/cards/${cardId}`);
  }
}
