# DealDirection

Dale Mexic Dale

DealDirection is a Romanian-language mobile app that helps shoppers **save money on their whole grocery cart**. It gathers offers from supermarkets, builds the cheapest shopping plan, guides the client to the store, and rewards them with points when a scanned receipt confirms the purchase.

**Status:** planning is finished, and the project skeleton is in place with no features built yet. This is the MVP for a 24-hour hackathon, built by a team of 4.

This README holds the product rules and technical reference. [TEAM_TASKS.md](TEAM_TASKS.md) holds the team plan and the details of all 19 build tasks.

## Run the app

You'll need Python 3.12, Node.js and PostgreSQL 16+ running. Scanning uses RapidOCR, which installs with the Python packages; Tesseract with Romanian language data is only needed if you set `OCR_ENGINE=tesseract`. You don't need to create the database: the backend creates it and any missing tables each time it starts.

Start in the repo root, and run the commands one at a time.

**Activate `.venv` in every new terminal that runs Python commands.** You'll see `(.venv)` in the prompt when it's active. Use the line for your terminal:

| Terminal       | Command                         |
| -------------- | ------------------------------- |
| Git Bash       | `source .venv/Scripts/activate` |
| PowerShell     | `.venv\Scripts\Activate.ps1`    |
| macOS or Linux | `source .venv/bin/activate`     |

**1. First time only: set up**

```bash
cp .env.example .env
```

Open `.env` and put your PostgreSQL password in `DATABASE_URL`. Then create `.venv`. On Windows:

```bash
py -3.12 -m venv .venv
```

On macOS or Linux, use `python3.12 -m venv .venv`. Activate it with the command for your terminal, then install everything:

```bash
source .venv/Scripts/activate
```

```bash
python -m pip install -r requirements.txt
```

```bash
cd frontend
```

```bash
npm install
```

```bash
cd ..
```

**2. Terminal 1: activate `.venv`, start the backend from the repo root and leave it running**

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

**3. Terminal 2: start the frontend and leave it running**

```bash
cd frontend
```

```bash
npx ng serve --proxy-config proxy.conf.json
```

**4. Test it**

- http://localhost:8000/api/health should show `{"status":"ok"}`.
- http://localhost:4200/api/health should show the same, which proves the frontend reaches the backend.
- http://localhost:4200 should open the app.

**5. Terminal 3: activate `.venv` and run the automated tests from the repo root**

```bash
pytest
```

```bash
cd frontend
```

```bash
npx ng test --watch=false
```

**Load the data:** once Task 5 is built, activate `.venv` and run this from the repo root while the backend is running, the first time and after any data change. Until then it does nothing.

```bash
python -m dealdata.load
```

[requirements.txt](requirements.txt) also lists the tools pip can't install.

## Demo goal

A presenter completes this loop live on a phone, using real scraped prices and a real receipt:

1. Build or import a shopping list.
2. See the cheapest split and the best single store.
3. Get directions to the store.
4. Scan the receipt.
5. See points added to the wallet.

## Scope

| Tier          | Features                                                                                                                                                   |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Must**      | Price data, product browsing, cart and optimiser, receipt scan with points, list import, store selection, saved lists, directions, simple login, demo user |
| **Should**    | Loyalty card wallet                                                                                                                                        |
| **Simulated** | Spending points, using a fake rewards page                                                                                                                 |
| **Out**       | Admin dashboard, live scraping, real partner integrations, multiple cities, per-store pricing, password reset, social login, other languages               |

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

| Result                             | Modifier                                  |
| ---------------------------------- | ----------------------------------------- |
| Paid less, or under 5% more        | x1.00 (full points)                       |
| Paid 5% or more above the estimate | `1 + difference`, so 12% over gives x1.12 |
| Maximum                            | x1.25                                     |

```text
points = round(E × POINTS_PER_LEI × modifier)
```

The extra points compensate clients who paid more because of regional prices. With the placeholder rate of 10 points per lei, a 100 lei list earns 1,000 points, and paying 112 lei earns 1,120. The 5% stays adjustable in the config.

Points can be spent on specific products at partner stores, online or in person. In the MVP this is simulated.

### Loyalty cards

The client uploads a photo of a card and crops it to the barcode or QR code. The app shows that code on a generic card, in a colour unique to the store, with its name or logo clearly visible.

### Lists

Clients can create, view, rename, edit and delete lists. A list is `draft`, `active` once a plan is chosen, or `completed` when every store part has a receipt or the client closes it.

A deleted list goes to the trash for 2 weeks, and can be restored until then. After that the client can't see it. The database only soft deletes lists by setting `deleted_at`, so a list's receipts stay stored and can't be used again.

## Technology

| Part        | Technology                                                                 |
| ----------- | -------------------------------------------------------------------------- |
| Frontend    | Angular PWA, Romanian only                                                 |
| Backend     | Python 3.12, FastAPI, SQLAlchemy                                           |
| Database    | PostgreSQL                                                                 |
| Data import | Python scripts, run offline                                                |
| Scanning    | RapidOCR (Tesseract as fallback), OpenCV, regular expressions, `rapidfuzz` |

FastAPI serves the Angular app and the `/api` routes from one HTTPS address.

### Scanning

Scanning uses **no AI service**, and everything runs on the backend machine.

1. **Crop the photo** with OpenCV: find the receipt, and straighten it when its corners are clear.
2. **Read the text** with RapidOCR's Romanian model, which runs locally through `onnxruntime`. PDFs with text use `pypdf`, and scanned PDFs are turned into images first.
3. **Parse the text** with regular expressions, using small rules per store.
4. **Match products** with `rapidfuzz`, scoring `0.7 × name similarity + 0.3 × price closeness`.

The weights and the minimum score of 70 are starting values. On real, creased receipt photos, Tesseract read almost nothing while RapidOCR read the store, date, total and every item, so RapidOCR is the default. Set `OCR_ENGINE=tesseract` to switch back. To compare engines on your own photos, run `uv run python scripts/ocr_check.py "<photo folder>"`.

Receipt photos are read and discarded, and only the extracted data is kept.

## Data

| Store      | Method                       | Status                                         |
| ---------- | ---------------------------- | ---------------------------------------------- |
| Auchan     | Public catalog JSON endpoint | Main source, tested with small requests only   |
| Carrefour  | Sitemap and category pages   | Second source, tested with small requests only |
| Lidl       | Website pages                | Optional third source                          |
| Mega Image | Not tested                   | Backup source                                  |

The team scrapes once, slowly, and demos from a saved snapshot of 150–300 products in about 30 categories. A block during the pitch can't affect it.

### Data import steps

1. Scrape once at no more than 1 request per second, and save the raw output in `data/raw/`.
2. Parse the size from each product name, and convert it to `l`, `kg` or `buc`.
3. Place products in the hand-checked tree. Keyword search alone isn't enough: a search for `lapte` returned a baby cleansing lotion first.
4. Save `data/snapshot/products.json`, and load it into Postgres. The load can be re-run safely, and also seeds store locations and the demo user.

Auchan's product search is `https://www.auchan.ro/api/catalog_system/pub/products/search?ft=lapte&_from=0&_to=9`. Prices are in `items[0].sellers[0].commertialOffer.Price`, and barcodes in `items[0].ean`. Carrefour's URLs come from `https://carrefour.ro/pub/sitemap/sitemap.xml`, its category pages hold prices in `data-price-amount`, and its `ajax` and `catalogsearch` paths are disallowed.

## Technical reference

### Architecture

```text
Phone (Angular PWA)
   │  HTTPS, /api and the built app, from one address
   ▼
FastAPI
   ├─ router.py files    HTTP, login checks, database reads and writes
   ├─ optimizer, points  pure logic, no database or HTTP
   └─ documents          OCR and parsing, behind the DocumentReader protocol
   ▼
PostgreSQL  ◄── dealdata load ◄── data/snapshot/products.json ◄── scrapers (offline)
```

The app has three parts, and each one can be worked on alone:

- **`frontend/`** only talks to the backend through `/api`. Until a route is ready, a screen can use mock data.
- **`backend/`** has one folder per unit, as listed in [Backend units](#backend-units). Business rules stay in the pure `logic.py` files, so they can be tested without a database.
- **`data/`** runs offline. The running app only reads what `dealdata.load` put in Postgres, so a blocked scraper can't break the demo.

### Where new code goes

| Adding                     | Put it in                                                                   |
| -------------------------- | --------------------------------------------------------------------------- |
| An API route               | The unit's `router.py`. `main.py` already mounts every router under `/api`. |
| A database table or column | `backend/app/models.py`                                                     |
| A setting                  | `backend/app/config.py`, and `.env.example` if it's a secret                |
| Business logic             | The unit's `logic.py`, with no database or HTTP code                        |
| An OCR engine change       | `backend/app/documents/ocr.py` only                                         |
| A screen                   | Its folder in `frontend/src/app/`, plus one line in `app.routes.ts`         |
| A call to the API          | One typed method in `frontend/src/app/core/api.ts`                          |
| Romanian text              | `frontend/src/app/shared/ro.ts`                                             |

Each placeholder file names its owner and task. Stay inside your own files where you can, because shared files like `models.py`, `api.ts`, `ro.ts` and `app.routes.ts` are the likeliest to conflict. Keep those changes small and merge them often.

### Project structure

```text
pyproject.toml, uv.lock, requirements.txt, .python-version, .env.example, .gitignore
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
frontend/proxy.conf.json
frontend/src/app/
  app.ts app.html app.scss app.routes.ts app.config.ts
  core/ (api, auth, auth.guard, auth.interceptor)  shared/ro.ts
  login/ browse/ cart/ plan/ import/ lists/ receipt/ wallet/ cards/ settings/
```

### Backend units

Each unit has one job, and can be tested without the others.

| Unit              | Input                         | Output                                       | Depends on                    |
| ----------------- | ----------------------------- | -------------------------------------------- | ----------------------------- |
| `auth`            | Login details                 | Signed token                                 | Database                      |
| `catalog`         | Category, search text, stores | Size-level products and generic prices       | Database                      |
| `lists`           | List changes                  | Saved lists and items                        | Database                      |
| `optimizer`       | Items, prices, stores         | Plans and missing items                      | Nothing: pure logic           |
| `documents`       | Image, PDF or text            | Structured receipt or food list, and matches | RapidOCR or Tesseract, OpenCV |
| `imports`         | Foods, days, product tree     | List items ready for review                  | `documents`                   |
| `receipts`        | Receipt, list items           | Matches and points                           | `documents`, `points`         |
| `points`          | Estimate, paid, config        | Modifier and points                          | Nothing: pure logic           |
| `wallet`, `cards` | Rewards and card images       | Point history and saved cards                | Database                      |

### Database tables

| Table             | Key fields                                                                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `users`           | email, password hash, is_demo                                                                                                              |
| `stores`          | name, colour, logo                                                                                                                         |
| `store_locations` | store, address, latitude, longitude                                                                                                        |
| `user_stores`     | user, store                                                                                                                                |
| `categories`      | parent, name, level (category, type or size), size_amount, size_unit, aliases                                                              |
| `store_products`  | store, size-level category, type category, name, brand, barcode, price, unit, image, source URL, search_text, updated_at                   |
| `shopping_lists`  | user, name, state, suggestion_shown, extra_store_id, created_at, deleted_at                                                                |
| `list_items`      | list, size-level category, chosen product (empty for generic), brand, quantity, assigned store, assigned product, estimated_price, removed |
| `receipts`        | list, store, fingerprint (unique), purchased_at, total, estimate, paid, modifier, points; unique on list and store                         |
| `receipt_lines`   | receipt, raw text, quantity, line total, matched list item                                                                                 |
| `points_ledger`   | user, amount, reason, receipt, created_at                                                                                                  |
| `loyalty_cards`   | user, store, code image; unique on user and store                                                                                          |

Create tables with `Base.metadata.create_all`, since a hackathon doesn't need migrations.

### API routes

All routes are under `/api`.

| Area       | Routes                                                                                                                 |
| ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| Health     | `GET /health`                                                                                                          |
| Login      | `POST /auth/register`, `POST /auth/login`, `POST /auth/demo`                                                           |
| Stores     | `GET /stores`, `PUT /me/stores`, `GET /stores/{id}/directions?lat=&lng=`                                               |
| Catalog    | `GET /categories?parent_id=`, `GET /categories/{id}/products?brand_q=`, `GET /search?q=`                               |
| Lists      | `POST /lists`, `GET /lists`, `GET /lists/{id}`, `PATCH /lists/{id}`, `DELETE /lists/{id}`, `POST /lists/{id}/complete` |
| List items | `POST /lists/{id}/items`, `PATCH /lists/{id}/items/{item_id}`, `DELETE /lists/{id}/items/{item_id}`                    |
| Plans      | `POST /lists/{id}/plans`, `POST /lists/{id}/suggestion/accept`, `POST /lists/{id}/activate`, `GET /lists/{id}/parts`   |
| Receipts   | `POST /lists/{id}/receipts?store_id=`                                                                                  |
| Import     | `POST /imports`, `POST /imports/confirm`                                                                               |
| Wallet     | `GET /wallet`, `GET /rewards`, `POST /rewards/{id}/redeem`                                                             |
| Cards      | `GET /cards`, `POST /cards`, `GET /cards/{id}/image`, `DELETE /cards/{id}`                                             |

### Configuration

All values live in backend config and can be changed without a code change.

| Setting                | Demo value                    |
| ---------------------- | ----------------------------- |
| `MARGIN`               | 0.05                          |
| `MAX_MODIFIER`         | 1.25                          |
| `POINTS_PER_LEI`       | 10 (placeholder)              |
| `MIN_SPLIT_SAVING_LEI` | 10 (placeholder)              |
| `TRASH_RETENTION_DAYS` | 14                            |
| `OCR_ENGINE`           | `rapidocr` (or `tesseract`)   |
| `OCR_RAPID_LANG`       | `ro`                          |
| `OCR_LANG`             | `ron+eng` (Tesseract only)    |
| `OCR_PSM`              | 4 (Tesseract only)            |
| `OCR_MIN_MATCH_SCORE`  | 70 (placeholder)              |
| `MAX_UPLOAD_MB`        | 10                            |
| `TESSERACT_CMD`        | Path to the Tesseract program |

`.env.example` lists `DATABASE_URL` and `JWT_SECRET`, the only values needed so far. When a task starts using `TESSERACT_CMD`, `DEFAULT_LAT`, `DEFAULT_LNG` or `DEMO_PASSWORD`, add that value to `.env.example` and tell the team to update their `.env`.

### Screens

All screens are in Romanian.

| Screen         | Purpose                                                                      |
| -------------- | ---------------------------------------------------------------------------- |
| Login          | Simple login with minimal details, and a demo user entry                     |
| Browse         | Category → type → size, generic price, brand search                          |
| Deals          | Seasonal offers and large discounts, opened from the Home screen             |
| Cart           | Items added by hand, from Home or by import, total, points, shops, directions, receipt scan |
| Plan           | Chosen plan by store, with directions and a receipt button per store         |
| Import         | One button for a PDF, picture or text, the number of days, the review screen |
| Lists          | Saved lists: view, edit, delete                                              |
| Receipt result | Matched and unmatched items, estimate, paid, modifier, points                |
| Wallet         | Points balance, history, simulated rewards                                   |
| Cards          | Card wallet and large code view                                              |
| Settings       | Store selection, logout                                                      |

### Error handling

| Situation                                             | What happens                                                                                    |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Receipt is unreadable, or OCR fails or takes too long | Nothing is saved, the client is asked to retake the photo, and the receipt can be scanned again |
| Receipt was already used                              | Rejected, with a clear message                                                                  |
| Part of a list already has a receipt                  | Rejected, so one part can't earn twice                                                          |
| Receipt is from the wrong store                       | Rejected, naming the expected store                                                             |
| No lines match                                        | Rejected, no points are given, and the receipt can be scanned again                             |
| Import finds nothing usable                           | The client is asked to try again or paste text                                                  |
| Import food can't be mapped                           | Flagged on the review screen                                                                    |
| Item has no price at any selected store               | Shown as unavailable in the cart                                                                |
| No stores selected, or an empty cart                  | A clear message, with no plans                                                                  |
| Location is denied                                    | The default location is used for directions                                                     |
| Camera is unavailable                                 | Falls back to a file picker                                                                     |
| File is too large or the wrong type                   | Rejected with a clear message                                                                   |

### Development rules

- All UI text is Romanian, kept in `frontend/src/app/shared/ro.ts`. Product names stay as published.
- Money and quantities use `Decimal` in Python and `NUMERIC` in Postgres, never floats.
- Config values are never hardcoded.
- Never store or log receipt images.
- Never commit `.env`, secrets or raw scrape output.
- The project has exactly one database, `dealdirection`, set by `DATABASE_URL`. Don't add a second database, a test database or a `TEST_DATABASE_URL` setting.
- Tests never drop tables or delete data in `dealdirection`. They only change data inside a transaction that is rolled back.
- Scrapers send a generic User-Agent and at most 1 request per second. If a site blocks them, stop and tell the team.
- Use Python 3.12 in `.venv`, because a newer default Python may lack prebuilt packages. Run Python commands from the repository root.

### Testing

- **Unit tests** cover `points` and `optimizer`.
- **Fixture tests** cover receipt parsing, matching and import using saved OCR text, so they don't need Tesseract.
- **API tests** use a fake reader and the project's one database, `dealdirection`. Each test runs inside a transaction that is rolled back, so it leaves no data behind.
- **Accuracy check:** 3–5 real receipts and the three import formats, reviewed by hand.
- **Real-world checks:** the Auchan price test, a cropped barcode at a real till, and the full demo on a real phone over HTTPS.

## Before building

- Read Auchan's and Carrefour's terms of use, since robots.txt isn't permission.
- Confirm the hackathon allows pre-scraped data and pre-written plans.
- Choose the demo city.
- Install PostgreSQL, Tesseract and `cloudflared`.
- Photograph 5 real receipts each from Auchan and Carrefour, and test OCR on them.
- Buy 5 products at Auchan, and compare the receipt with the online prices.
- Test a cropped card barcode at a real till.

## Known risks

| Risk                                                    | Plan                                                                    |
| ------------------------------------------------------- | ----------------------------------------------------------------------- |
| OCR reads crumpled or faded receipts badly              | Test early, use good light for the demo, and keep RapidOCR as a backup  |
| A store blocks scraping                                 | Use the saved snapshot, or Mega Image as a backup                       |
| Online and shelf prices differ widely                   | The modifier gives extra points, and the Auchan test shows the real gap |
| A cropped barcode doesn't scan at the till              | Label the wallet display-only in the demo                               |
| A client builds a list from a receipt they already have | Accepted for the demo                                                   |
| Live demo failure                                       | Keep a seeded demo user and a backup video                              |

## Open decisions

These don't block the MVP, and use placeholders for now:

- The final points system and base rate.
- Who funds the points.
- The demo city.
- The minimum saving for a split.
