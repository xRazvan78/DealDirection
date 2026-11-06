# DealDirection: MVP design

**Date:** 2026-11-06
**Status:** Approved
**Scope:** The MVP for a 24-hour hackathon, built by an assumed team of 3–4 people.

## 1. Goal

DealDirection is a Romanian-language mobile PWA that helps shoppers **save money on their whole grocery cart**. It compares supermarket prices, builds the cheapest shopping plan, and rewards the client with points when a receipt confirms the purchase.

The demo succeeds if a presenter can complete this loop live on a phone, using real scraped prices and a real receipt:

1. Build or import a shopping list.
2. See the cheapest split and the best single store.
3. Get directions to the store.
4. Scan the receipt.
5. See points added to the wallet.

## 2. Scope

### In scope

| Tier | Features |
|---|---|
| **Must** | Price data, product browsing, cart and optimiser, receipt scan with points, list import, store selection, saved lists, directions, simple login, demo user |
| **Should** | Loyalty card wallet |
| **Simulated** | Spending points, using a fake rewards page |

If the team falls behind, cut the card wallet first, then PDF import.

### Out of scope

- Admin dashboard. Changes are made internally through config and the database.
- Live or scheduled scraping.
- Real partner integrations and the points funding model.
- Multiple cities and per-store pricing.
- Registration extras such as password reset and social login.
- Any language other than Romanian. Product names stay as the stores publish them.

## 3. Product rules

### 3.1 Product structure

Products are organised as **category → type → size**, for example `Lapte → 3.5% → 1 l` or `Lapte → Ovăz → 1 l`.

- The bottom level (size) is the unit of comparison. Products at this level are treated as interchangeable.
- The **generic option** is the lowest-priced product at that level across the client's selected stores.
- A client can add the generic option, or search that level for a specific brand and add that instead.

### 3.2 Prices

All prices come from the stores' online shops. The app does not claim to show shelf prices. Each price displays its update date.

### 3.3 Store selection

- The client chooses which stores count. Unselected stores are left out of every price and calculation.
- Store selection is independent of the loyalty cards the client has saved.
- The app may show **one** suggestion per shopping list for an unselected store: the store that gives the largest total saving. Once shown, it never appears again on that list. Accepting it adds the store for that list only.

### 3.4 Cart results

The cart shows up to two plans:

- **Best single store:** the selected store with the lowest total.
- **Cheapest split:** each item goes to its cheapest selected store.

The split appears only if it saves at least `MIN_SPLIT_SAVING_LEI` compared with the best single store. Otherwise the single store appears alone, with a note that splitting isn't worth it.

If a store doesn't carry every item, the app **asks about each missing item in turn**. The client picks a replacement from the same type at that store, or removes the item from that plan. Totals update after each choice.

A brand item counts as available only at stores that sell that brand at the same size level.

### 3.5 Directions

Each store in a plan has a directions button that opens Google Maps at the nearest seeded location for that store. Nearest is worked out from the browser's location, and falls back to a default location in the demo city.

### 3.6 List import

One button accepts **one** of the following per import: a PDF, a picture, or pasted text. It accepts either a shopping list or a nutrition plan.

1. The client uploads the file or pastes the text, and sets the number of days to shop for.
2. The app extracts the foods and quantities.
3. The app scales quantities to the chosen period, and adds up repeated foods.
4. The app maps each food to a size-level product, rounding up to whole packs.
5. A review screen shows the result. Foods it couldn't map are flagged for the client to pick or remove.
6. The client confirms, and the items are added to a new list.

Example: `200g piept de pui zilnic` for 7 days becomes 1.4 kg, which is rounded up to real pack sizes.

Imports must handle typed or printed content. Handwriting isn't a demo requirement.

### 3.7 Receipts

Each store's part of a list is checked separately: it has its own receipt, ~5% check and points. A list that is split across two stores therefore needs two receipts.

1. The client photographs the receipt for one store's part of the list.
2. The app reads the store, date, time, total and item lines.
3. The app rejects the receipt if its fingerprint has already been used, or if the store doesn't match that part of the list.
4. The app matches receipt lines to list items. A generic item accepts any brand at the same size level. A brand item must match that brand.
5. Only matched items earn points. Missing items and extra receipt lines earn nothing.

**Anti-cheat:** each receipt can be used once, using a hash of store, date, time and total as its fingerprint. This is the only rule in the MVP. A client could still build a list from a receipt they already have. That's an accepted demo risk.

### 3.8 Points

For the matched items on one receipt:

- `E` = the app's estimate: online price × quantity, summed.
- `P` = the amount paid: receipt line totals, summed.
- `diff` = `(P - E) / E`.

```text
if diff < MARGIN:  modifier = 1.00
else:              modifier = min(1 + diff, MAX_MODIFIER)

points = round(E × POINTS_PER_LEI × modifier)
```

| Estimate `E` | Paid `P` | `diff` | Modifier | Points at 10 per lei |
|---|---|---|---|---|
| 100 lei | 90 lei | -10% | x1.00 | 1,000 |
| 100 lei | 103 lei | +3% | x1.00 | 1,000 |
| 100 lei | 105 lei | +5% | x1.05 | 1,050 |
| 100 lei | 112 lei | +12% | x1.12 | 1,120 |
| 100 lei | 140 lei | +40% | x1.25 | 1,250 |

The modifier compensates clients who paid more because of regional prices.

**Open items:** the final points system isn't decided. `POINTS_PER_LEI` is a demo placeholder, chosen so totals reach the hundreds and thousands. These two interpretations are assumptions:

- Paying up to, but not including, 5% over the estimate earns full points.
- Points are calculated on the estimate `E`, not the amount paid, so the modifier is the only extra.

### 3.9 Spending points

Points are simulated. The wallet shows a balance and a history. A fake rewards page lists sample products that "spend" points by adding a negative entry to the history. No partner store is involved.

### 3.10 Loyalty card wallet

- The client uploads a photo of a loyalty card and crops it to the barcode or QR code.
- The app shows that image on a generic card design, with the store's name or logo clearly visible.
- Each store has its own colour, so cards are easy to tell apart.
- Opening a card shows the code large enough to scan at the till.

### 3.11 Lists

Clients can create, view, rename, edit and delete shopping lists. A list has one of these states:

| State | Meaning |
|---|---|
| `draft` | Being edited |
| `active` | A plan was chosen and the store parts are fixed |
| `completed` | Every store part has an accepted receipt, or the client closed the list |

## 4. Architecture

| Part | Technology | Responsibility |
|---|---|---|
| Frontend | Angular PWA | All screens, camera and file input, HTTPS-only deployment |
| Backend | Python, FastAPI | API, login, optimiser, matching, points |
| Database | PostgreSQL | All app data |
| Data import | Python scripts | Scrape stores, normalise, load into Postgres |
| Document reader | Claude API, default model `claude-sonnet-5-5`, set through config | Read receipts and imports, and map foods to products |

```text
Angular PWA ──HTTPS──> FastAPI ──> PostgreSQL
                          │             ▲
                          ▼             │
                      Claude API   Data import scripts (run offline)
```

### Backend units

Each unit has one job, and can be tested without the others.

| Unit | Input | Output | Depends on |
|---|---|---|---|
| `auth` | Login details | Signed token | Database |
| `catalog` | Category, search text, stores | Size-level products and generic prices | Database |
| `lists` | List changes | Saved lists and items | Database |
| `optimizer` | Items, prices, stores | Plans and missing items | Nothing: pure logic |
| `documents` | Image, PDF or text | Structured receipt or food list | Claude API |
| `import_mapper` | Foods, days, product tree | List items ready for review | `documents` |
| `receipt_matcher` | Receipt lines, list items | Matched pairs | `documents` |
| `points` | Matched pairs, config | Modifier and points | Nothing: pure logic |
| `wallet` | Rewards and cards | Point history and saved cards | Database |

### Repository layout

```text
frontend/   Angular PWA
backend/    FastAPI app, with one package per unit
data/       Scrapers, normalisation and the category tree
docs/       Specs and plans
```

## 5. Data

### 5.1 Sources

| Store | Method | Status |
|---|---|---|
| Auchan | Public catalog JSON endpoint | Main source. One small test returned name, brand, barcode, price and stock |
| Carrefour | Sitemap and category page HTML | Second source. One category page contained prices |
| Lidl | Website pages | Stretch third source. Prices were seen on the homepage only |

Bulk scraping is untested, and each site's terms of use must be read before scraping.

### 5.2 Import pipeline

1. Scrape once at a low request rate. Save the raw output.
2. Parse the size from each product name, and convert it to a standard unit.
3. Place products in a hand-checked tree of about 30 categories, with 150–300 products in total. Keyword search alone isn't enough: a search for `lapte` returned a baby cleansing lotion first.
4. Load the result into Postgres. The load can be re-run safely.

The demo uses this saved snapshot, so a block during the pitch can't affect it. Seeded data also includes store locations for the demo city and the demo user.

### 5.3 Main tables

| Table | Key fields |
|---|---|
| `users` | email, password hash, is_demo |
| `stores` | name, colour, logo |
| `store_locations` | store, address, latitude, longitude |
| `user_stores` | user, store |
| `categories` | parent, name, level (category, type or size) |
| `store_products` | store, size-level category, name, brand, barcode, price, unit, image, source URL, updated_at |
| `shopping_lists` | user, name, state, suggestion_shown |
| `list_items` | list, size-level category, chosen product (empty for generic), quantity, assigned store |
| `receipts` | list, store, fingerprint (unique), purchased_at, total, estimate, paid, modifier, points |
| `receipt_lines` | receipt, raw text, quantity, line total, matched list item |
| `points_ledger` | user, amount, reason, receipt, created_at |
| `loyalty_cards` | user, store, code image |

### 5.4 Config

All values live in backend config and can be changed without a code change.

| Setting | Demo value |
|---|---|
| `MARGIN` | 0.05 |
| `MAX_MODIFIER` | 1.25 |
| `POINTS_PER_LEI` | 10 (placeholder) |
| `MIN_SPLIT_SAVING_LEI` | 10 (placeholder) |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` |

## 6. Screens

All screens are in Romanian.

| Screen | Purpose |
|---|---|
| Login | Simple login with minimal details, and a demo user entry |
| Browse | Category → type → size, generic price, brand search |
| Cart | Items, plans, missing-item prompts, the unselected-store suggestion |
| Plan | Chosen plan by store, with directions and a receipt button per store |
| Import | One button for a PDF, picture or text, the number of days, the review screen |
| Lists | Saved lists: view, edit, delete |
| Receipt result | Matched and unmatched items, estimate, paid, modifier, points |
| Wallet | Points balance, history, simulated rewards |
| Cards | Card wallet and large code view |
| Settings | Store selection, logout |

## 7. Error handling

| Situation | What happens |
|---|---|
| Receipt is unreadable | Nothing is saved. The client is asked to retake the photo. The fingerprint isn't used up |
| Receipt was already used | Rejected, with a clear message |
| Receipt is from the wrong store | Rejected, naming the expected store |
| No lines match | The receipt is rejected, no points are given, and the fingerprint isn't used up |
| Claude API fails or times out | The client can retry, and the list and cart aren't affected |
| Import finds nothing usable | The client is asked to try again or paste text |
| Import food can't be mapped | Flagged on the review screen |
| Item has no price at any selected store | Shown as unavailable in the cart |
| Location is denied | The default location is used for directions |
| Camera is unavailable | Falls back to a file picker |

Uploaded receipt images are read and then discarded. Only the parsed data is kept, because receipts can contain personal data.

## 8. Testing

- **Unit tests** for `points`, covering every row in the table in section 3.8, and for `optimizer`, covering single store, split, minimum saving, missing items and brand items.
- **Fixture tests** for `receipt_matcher` and `import_mapper`, using saved structured outputs so they don't call the Claude API.
- **Accuracy check** using 3–5 real receipts and the three import formats, reviewed by hand.
- **Real-world checks before the event:**
  - Buy 5 products at Auchan and compare the receipt with the online prices.
  - Test a cropped card barcode at a real till.
  - Run the full demo on a real phone over HTTPS.

## 9. 24-hour plan

| Hours | Goal |
|---|---|
| 0–2 | Agree the data model and API, split the work |
| 2–8 | Data import, login, category browsing |
| 8–14 | Cart, optimiser, store selection, lists, directions |
| 14–19 | Document reader, receipt matching, points, list import |
| 19–21 | Card wallet and simulated rewards, only if the main loop works |
| 21–23 | Feature freeze, bug fixes, demo data, backup video |
| 23–24 | Pitch rehearsal |

## 10. Risks

| Risk | Mitigation |
|---|---|
| A site blocks scraping | Use the saved snapshot, with Mega Image as a backup source |
| Terms of use forbid scraping | Read them first, and limit use to a small demo snapshot |
| Online and shelf prices differ widely | The modifier gives extra points, and the pre-event test shows how wide the gap is |
| Abbreviated receipt names don't match | Use a prepared demo receipt, and review results before the pitch |
| A cropped barcode doesn't scan | Test at a till, and treat the wallet as display-only in the demo if it fails |
| Scope is too large for the time | Follow the cut order in section 2 |
| Live demo failure | Keep a seeded demo user and a backup video |

## 11. Open decisions

These don't block the MVP. They use the placeholders above until they're decided.

- The final points system and base rate.
- Who funds the points.
- The team size. The plan assumes 3–4 people, and scope should shrink if the team is smaller.
- The demo city.
- The value of `MIN_SPLIT_SAVING_LEI`.
