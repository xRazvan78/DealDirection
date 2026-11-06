# DealDirection

DealDirection is a Romanian-language mobile app that helps shoppers **save money on their whole grocery cart**. It gathers offers from supermarkets, builds the cheapest shopping plan, guides the client to the store, and rewards them with points when a scanned receipt confirms the purchase.

**Status:** planning is finished and no application code exists yet. This is the MVP for a 24-hour hackathon, built by a team of 4.

This README holds the product rules and technical reference. [TEAM_TASKS.md](TEAM_TASKS.md) holds the team plan and the details of all 19 build tasks.

## Demo goal

A presenter completes this loop live on a phone, using real scraped prices and a real receipt:

1. Build or import a shopping list.
2. See the cheapest split and the best single store.
3. Get directions to the store.
4. Scan the receipt.
5. See points added to the wallet.

## Scope

| Tier | Features |
|---|---|
| **Must** | Price data, product browsing, cart and optimiser, receipt scan with points, list import, store selection, saved lists, directions, simple login, demo user |
| **Should** | Loyalty card wallet |
| **Simulated** | Spending points, using a fake rewards page |
| **Out** | Admin dashboard, live scraping, real partner integrations, multiple cities, per-store pricing, password reset, social login, other languages |

If the team falls behind, cut the card wallet first, then PDF import.

## How the app works

### Products

Products are organised as **category → type → size**, such as `Lapte → 3.5% → 1 l` or `Lapte → Ovăz → 1 l`. Products at the size level are directly comparable.

The client adds either the **cheapest generic option** at that level, or searches for a specific brand.

### Prices

All prices come from the stores' online shops, and each one shows its update date. The app doesn't claim to show shelf prices.

### Store selection

The client chooses which stores count, and other stores are left out of every calculation. This is separate from the loyalty cards they've saved.

The app may suggest one cheaper unselected store **once per shopping list**. Accepting it adds that store for that list only.

### Cart

The cart compares two plans:

- **Best single store:** everything in one place.
- **Cheapest split:** each item at its cheapest selected store.

The split only appears if it saves at least 10 lei (a placeholder). If a store doesn't carry an item, the app asks about each missing item in turn, and the client picks a replacement or removes it.

### Directions

Each store in a plan has a button that opens Google Maps at its nearest location.

### List import

One button takes **one** PDF, picture or copied text message, containing a shopping list or nutrition plan. The client sets how many days to shop for.

The app scales the quantities, rounds up to real pack sizes, and shows a review screen before creating the list. For example, `200g piept de pui zilnic` for 7 days becomes 1.4 kg, which is rounded up to whole packs. Handwriting isn't supported.

### Receipts and points

Each store's part of a list has its own receipt, price check and points, so a list split across two stores needs two receipts. Only matched items earn points, and each receipt can only be used once.

For the matched items on a receipt, with `E` as the app's estimate and `P` as the amount paid:

| Result | Modifier |
|---|---|
| Paid less, or under 5% more | x1.00 (full points) |
| Paid 5% or more above the estimate | `1 + difference`, so 12% over gives x1.12 |
| Maximum | x1.25 |

```text
points = round(E × POINTS_PER_LEI × modifier)
```

The extra points compensate clients who paid more because of regional prices. With the placeholder rate of 10 points per lei, a 100 lei list earns 1,000 points, and paying 112 lei earns 1,120. The 5% stays adjustable in the config.

Points can be spent on specific products at partner stores, online or in person. In the MVP this is simulated.

### Loyalty cards

The client uploads a photo of a card and crops it to the barcode or QR code. The app shows that code on a generic card, in a colour unique to the store, with its name or logo clearly visible.

### Lists

Clients can create, view, rename, edit and delete lists. A list is `draft`, `active` once a plan is chosen, or `completed` when every store part has a receipt or the client closes it.

## Technology

| Part | Technology |
|---|---|
| Frontend | Angular PWA, Romanian only |
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Data import | Python scripts, run offline |
| Scanning | Tesseract, OpenCV, regular expressions, `rapidfuzz` |

FastAPI serves the Angular app and the `/api` routes from one HTTPS address.

### Scanning

Scanning uses **no AI service**, and everything runs on the backend machine.

1. **Clean the photo** with OpenCV: find the receipt, straighten it, and sharpen it.
2. **Read the text** with Tesseract in Romanian. PDFs with text use `pypdf`, and scanned PDFs are turned into images first.
3. **Parse the text** with regular expressions, using small rules per store.
4. **Match products** with `rapidfuzz`, scoring `0.7 × name similarity + 0.3 × price closeness`.

The weights and the minimum score of 70 are starting values. RapidOCR is the backup if Tesseract reads real receipts poorly.

Receipt photos are read and discarded, and only the extracted data is kept.

## Data

| Store | Method | Status |
|---|---|---|
| Auchan | Public catalog JSON endpoint | Main source, tested with small requests only |
| Carrefour | Sitemap and category pages | Second source, tested with small requests only |
| Lidl | Website pages | Optional third source |
| Mega Image | Not tested | Backup source |

The team scrapes once, slowly, and demos from a saved snapshot of 150–300 products in about 30 categories. A block during the pitch can't affect it.

### Data import steps

1. Scrape once at no more than 1 request per second, and save the raw output in `data/raw/`.
2. Parse the size from each product name, and convert it to `l`, `kg` or `buc`.
3. Place products in the hand-checked tree. Keyword search alone isn't enough: a search for `lapte` returned a baby cleansing lotion first.
4. Save `data/snapshot/products.json`, and load it into Postgres. The load can be re-run safely, and also seeds store locations and the demo user.

Auchan's product search is `https://www.auchan.ro/api/catalog_system/pub/products/search?ft=lapte&_from=0&_to=9`. Prices are in `items[0].sellers[0].commertialOffer.Price`, and barcodes in `items[0].ean`. Carrefour's URLs come from `https://carrefour.ro/pub/sitemap/sitemap.xml`, its category pages hold prices in `data-price-amount`, and its `ajax` and `catalogsearch` paths are disallowed.

## Technical reference

### Project structure

```text
pyproject.toml, .python-version, .env.example, .gitignore
backend/app/
  main.py config.py db.py models.py textutil.py deps.py
  auth/router.py   catalog/router.py   lists/router.py
  plans/router.py  plans/geo.py        optimizer/logic.py
  points/logic.py
  documents/ (schemas ocr receipt_parser food_parser fuzzy reader).py
  receipts/matching.py receipts/router.py
  imports/mapping.py   imports/router.py
  wallet/router.py wallet/rewards.py  cards/router.py
data/dealdata/
  normalize.py tree.py scrape_auchan.py scrape_carrefour.py scrape.py load.py
data/tree.yaml  data/abbreviations.yaml  data/stores.yaml  data/snapshot/products.json
tests/conftest.py  tests/backend/  tests/data/  tests/fixtures/
frontend/src/app/
  core/ (api, auth, guard, interceptor)  shared/ro.ts
  login/ browse/ cart/ plan/ import/ lists/ receipt/ wallet/ cards/ settings/
```

### Backend units

Each unit has one job, and can be tested without the others.

| Unit | Input | Output | Depends on |
|---|---|---|---|
| `auth` | Login details | Signed token | Database |
| `catalog` | Category, search text, stores | Size-level products and generic prices | Database |
| `lists` | List changes | Saved lists and items | Database |
| `optimizer` | Items, prices, stores | Plans and missing items | Nothing: pure logic |
| `documents` | Image, PDF or text | Structured receipt or food list, and matches | Tesseract, OpenCV |
| `imports` | Foods, days, product tree | List items ready for review | `documents` |
| `receipts` | Receipt, list items | Matches and points | `documents`, `points` |
| `points` | Estimate, paid, config | Modifier and points | Nothing: pure logic |
| `wallet`, `cards` | Rewards and card images | Point history and saved cards | Database |

### Database tables

| Table | Key fields |
|---|---|
| `users` | email, password hash, is_demo |
| `stores` | name, colour, logo |
| `store_locations` | store, address, latitude, longitude |
| `user_stores` | user, store |
| `categories` | parent, name, level (category, type or size), size_amount, size_unit, aliases |
| `store_products` | store, size-level category, type category, name, brand, barcode, price, unit, image, source URL, search_text, updated_at |
| `shopping_lists` | user, name, state, suggestion_shown, extra_store_id |
| `list_items` | list, size-level category, chosen product (empty for generic), brand, quantity, assigned store, assigned product, estimated_price, removed |
| `receipts` | list, store, fingerprint (unique), purchased_at, total, estimate, paid, modifier, points; unique on list and store |
| `receipt_lines` | receipt, raw text, quantity, line total, matched list item |
| `points_ledger` | user, amount, reason, receipt, created_at |
| `loyalty_cards` | user, store, code image; unique on user and store |

Create tables with `Base.metadata.create_all`, since a hackathon doesn't need migrations.

### API routes

All routes are under `/api`.

| Area | Routes |
|---|---|
| Health | `GET /health` |
| Login | `POST /auth/register`, `POST /auth/login`, `POST /auth/demo` |
| Stores | `GET /stores`, `PUT /me/stores`, `GET /stores/{id}/directions?lat=&lng=` |
| Catalog | `GET /categories?parent_id=`, `GET /categories/{id}/products?brand_q=`, `GET /search?q=` |
| Lists | `POST /lists`, `GET /lists`, `GET /lists/{id}`, `PATCH /lists/{id}`, `DELETE /lists/{id}`, `POST /lists/{id}/complete` |
| List items | `POST /lists/{id}/items`, `PATCH /lists/{id}/items/{item_id}`, `DELETE /lists/{id}/items/{item_id}` |
| Plans | `POST /lists/{id}/plans`, `POST /lists/{id}/suggestion/accept`, `POST /lists/{id}/activate`, `GET /lists/{id}/parts` |
| Receipts | `POST /lists/{id}/receipts?store_id=` |
| Import | `POST /imports`, `POST /imports/confirm` |
| Wallet | `GET /wallet`, `GET /rewards`, `POST /rewards/{id}/redeem` |
| Cards | `GET /cards`, `POST /cards`, `GET /cards/{id}/image`, `DELETE /cards/{id}` |

### Configuration

All values live in backend config and can be changed without a code change.

| Setting | Demo value |
|---|---|
| `MARGIN` | 0.05 |
| `MAX_MODIFIER` | 1.25 |
| `POINTS_PER_LEI` | 10 (placeholder) |
| `MIN_SPLIT_SAVING_LEI` | 10 (placeholder) |
| `OCR_LANG` | `ron+eng` |
| `OCR_PSM` | 4 |
| `OCR_MIN_MATCH_SCORE` | 70 (placeholder) |
| `MAX_UPLOAD_MB` | 10 |
| `TESSERACT_CMD` | Path to the Tesseract program |

`.env.example` lists `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `TESSERACT_CMD`, `DEFAULT_LAT`, `DEFAULT_LNG` and `DEMO_PASSWORD`.

### Screens

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

### Error handling

| Situation | What happens |
|---|---|
| Receipt is unreadable, or OCR fails or takes too long | Nothing is saved, the client is asked to retake the photo, and the receipt can be scanned again |
| Receipt was already used | Rejected, with a clear message |
| Part of a list already has a receipt | Rejected, so one part can't earn twice |
| Receipt is from the wrong store | Rejected, naming the expected store |
| No lines match | Rejected, no points are given, and the receipt can be scanned again |
| Import finds nothing usable | The client is asked to try again or paste text |
| Import food can't be mapped | Flagged on the review screen |
| Item has no price at any selected store | Shown as unavailable in the cart |
| No stores selected, or an empty cart | A clear message, with no plans |
| Location is denied | The default location is used for directions |
| Camera is unavailable | Falls back to a file picker |
| File is too large or the wrong type | Rejected with a clear message |

### Development rules

- All UI text is Romanian, kept in `frontend/src/app/shared/ro.ts`. Product names stay as published.
- Money and quantities use `Decimal` in Python and `NUMERIC` in Postgres, never floats.
- Config values are never hardcoded.
- Never store or log receipt images.
- Never commit `.env`, secrets or raw scrape output.
- Scrapers send a generic User-Agent and at most 1 request per second. If a site blocks them, stop and tell the team.
- Use Python 3.12 through uv, because this machine's default Python 3.15 may lack prebuilt packages. Run Python commands from the repository root.

### Testing

- **Unit tests** cover `points` and `optimizer`.
- **Fixture tests** cover receipt parsing, matching and import using saved OCR text, so they don't need Tesseract.
- **API tests** use a fake reader, and a real test database.
- **Accuracy check:** 3–5 real receipts and the three import formats, reviewed by hand.
- **Real-world checks:** the Auchan price test, a cropped barcode at a real till, and the full demo on a real phone over HTTPS.

## Getting started

These steps describe the planned setup, since the code doesn't exist yet.

You'll need [uv](https://docs.astral.sh/uv/), Node.js, PostgreSQL 16+, and Tesseract with Romanian language data.

```bash
cp .env.example .env
```

```bash
uv sync
```

```bash
uv run python -m dealdata.load
```

```bash
uv run uvicorn app.main:app --app-dir backend --reload --port 8000
```

```bash
cd frontend && npm install && npx ng serve --proxy-config proxy.conf.json
```

To run the tests:

```bash
uv run pytest
```

```bash
cd frontend && npx ng test --watch=false
```

## Before building

- Read Auchan's and Carrefour's terms of use, since robots.txt isn't permission.
- Confirm the hackathon allows pre-scraped data and pre-written plans.
- Choose the demo city.
- Install PostgreSQL, Tesseract and `cloudflared`.
- Photograph 5 real receipts each from Auchan and Carrefour, and test OCR on them.
- Buy 5 products at Auchan, and compare the receipt with the online prices.
- Test a cropped card barcode at a real till.

## Known risks

| Risk | Plan |
|---|---|
| OCR reads crumpled or faded receipts badly | Test early, use good light for the demo, and keep RapidOCR as a backup |
| A store blocks scraping | Use the saved snapshot, or Mega Image as a backup |
| Online and shelf prices differ widely | The modifier gives extra points, and the Auchan test shows the real gap |
| A cropped barcode doesn't scan at the till | Label the wallet display-only in the demo |
| A client builds a list from a receipt they already have | Accepted for the demo |
| Live demo failure | Keep a seeded demo user and a backup video |

## Open decisions

These don't block the MVP, and use placeholders for now:

- The final points system and base rate.
- Who funds the points.
- The demo city.
- The minimum saving for a split.
