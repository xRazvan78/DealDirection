// API types, taken from TEAM_TASKS.md. Money and quantities are strings, so they
// never pass through a float.
//
// TEAM_TASKS.md doesn't define the types marked "Assumed", so confirm them with
// Member 2 when the route is built.

export interface Credentials {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
}

// Assumed: the fields, and `selected` for the client's store selection.
export interface Store {
  id: number;
  name: string;
  colour: string;
  logo: string | null;
  selected: boolean;
}

export interface Directions {
  address: string;
  maps_url: string;
}

// Assumed.
export interface Category {
  id: number;
  parent_id: number | null;
  name: string;
  level: 'category' | 'type' | 'size';
}

export interface Product {
  id: number;
  store_id: number;
  store_name: string;
  name: string;
  brand: string | null;
  price: string;
  image_url: string | null;
  updated_at: string;
}

// Assumed: `generic` has the same fields as a product.
export interface CategoryProducts {
  generic: Product | null;
  products: Product[];
}

export interface SearchResult {
  size_category_id: number;
  path: string;
  generic: Product | null;
}

export type ListState = 'draft' | 'active' | 'completed';

// Assumed.
export interface ListItem {
  id: number;
  size_category_id: number;
  chosen_product_id: number | null;
  brand: string | null;
  quantity: string;
  removed: boolean;
}

// Assumed.
export interface ShoppingList {
  id: number;
  name: string;
  state: ListState;
  items: ListItem[];
}

export interface NewListItem {
  size_category_id: number;
  quantity: string;
  chosen_product_id?: number;
}

export interface Resolution {
  item_id: number;
  store_id: number;
  replacement_product_id: number | null;
}

// Assumed: follows the optimiser's dataclasses in Task 3.
export interface Assignment {
  item_id: number;
  store_id: number;
  offer: Product;
  line_total: string;
}

export interface Plan {
  kind: 'single' | 'split';
  total: string;
  assignments: Assignment[];
}

export interface MissingItem {
  item_id: number;
  store_id: number;
  options: Product[];
}

export interface Suggestion {
  store_id: number;
  saving: string;
}

export interface PlanResult {
  single: Plan | null;
  split: Plan | null;
  split_saving: string;
  missing: MissingItem[];
  unavailable: number[];
  suggestion: Suggestion | null;
}

export interface ListPart {
  store_id: number;
  store_name: string;
  items: ListItem[];
  estimate: string;
  receipt_done: boolean;
}

// Assumed: the fields inside `matched` and `unmatched_items`.
export interface ReceiptResult {
  matched: { name: string; line_total: string }[];
  unmatched_items: { name: string }[];
  estimate: string;
  paid: string;
  modifier: string;
  points: number;
}

export interface ImportPreview {
  items: { food: string; size_category_id: number; path: string; packs: number }[];
  unmapped: string[];
}

export interface ImportConfirmation {
  name: string;
  items: { size_category_id: number; packs: number }[];
}

export interface Wallet {
  balance: number;
  history: { amount: number; reason: string; created_at: string }[];
}

export interface Reward {
  id: number;
  name: string;
  cost: number;
}

// Assumed.
export interface LoyaltyCard {
  id: number;
  store_id: number;
}
