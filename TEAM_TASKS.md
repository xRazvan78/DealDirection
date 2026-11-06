# DealDirection team tasks

This is the 24-hour plan for a team of 4. Replace "Member 1–4" with your names, and swap roles to suit your skills.

The [Task details](#task-details) section at the end describes all 19 tasks. The product rules, data model, API routes and configuration are in [README.md](README.md).

## Team overview

| Member | Role | Owns | Plan tasks |
|---|---|---|---|
| Member 1 | Data and supporting screens | Scrapers, product tree, lists and import screens, card wallet | 4, 5, 16, 18 |
| Member 2 | Backend lead | Database, login, catalog, lists, optimiser, plans, wallet API, final integration | 1, 6, 7, 3, 8, 9, 13 |
| Member 3 | Scanning and points | OCR, receipt parsing, matching, points, list import | 2, 10, 11, 12 |
| Member 4 | Frontend lead and pitch | App shell, login, browse, cart, plan, receipt and wallet screens, pitch | 14, 15, 17 |

## Timeline

| Hours | Member 1 | Member 2 | Member 3 | Member 4 |
|---|---|---|---|---|
| 0–2 | Draft the category tree | Task 1: skeleton and database | Check Tesseract, prepare receipts | Create the Angular project, sketch screens |
| 2–6 | Tasks 4–5: tree, scrapers | Tasks 6–7: login, catalog | Task 2, then Task 10 OCR test | Task 14: shell, login, settings |
| 6–8 | Task 5: load the snapshot | Task 3: optimiser | Task 10: reader | Task 15: browse |
| 8–11 | Task 16: lists screen | Task 3, then Task 8: lists | Task 10: reader | Task 15: cart |
| 11–14 | Task 16: import screen | Task 9: plans, directions | Task 11: receipts | Task 15: plan screen |
| 14–16 | Abbreviations and aliases | Task 13: wallet, cards API | Task 11: receipts | Task 17: receipt screen |
| 16–19 | Task 18: card wallet | Connect all screens to the API | Task 12: list import | Task 17: wallet screen |
| 19–21 | Finish Task 18, clean demo data | Fix integration bugs | Tune OCR on real receipts | Polish the phone layout and PWA |
| 21–23 | **Feature freeze:** Task 19 | Task 19 | Task 19 | Task 19 |
| 23–24 | Rehearse | Rehearse | Rehearse | Rehearse |

## Checkpoints

Stop for 10 minutes at each one, and make a cut if you're behind.

| Hour | What must work | If not |
|---|---|---|
| 2 | The API is agreed and the skeleton runs on every laptop | Member 2 fixes this before anything else |
| 8 | Real products can be browsed, and the OCR test result is known | Use a smaller product set, or try RapidOCR |
| 14 | A cart produces plans and opens directions | Everyone helps finish this first |
| 19 | The full loop works once, even if rough | Drop the card wallet |
| 21 | Feature freeze | Drop PDF import if it's unstable, and stop adding features |

## Member 1: Data and supporting screens

**Goal:** real, clean prices in the database, plus the lists, import and card screens.

**Before the event**
- [ ] Read Auchan's and Carrefour's terms of use, and report any problem to the team.
- [ ] Check the hackathon allows pre-scraped data.
- [ ] Run a small test scrape of both stores.

**During the event**
- [ ] Task 4: write `data/tree.yaml` with about 30 categories, and the size parser and classifier.
- [ ] Task 5: build the scrapers, save the snapshot, and load it with store locations and the demo user.
- [ ] Task 16: build the lists and import screens, using mock data until the API is ready.
- [ ] Help Member 3 with `data/abbreviations.yaml` and the tree's food aliases.
- [ ] Task 18: build the card wallet. It's the first feature to cut.
- [ ] Task 19: prepare the demo data, and test a cropped barcode at a real till.

**Depends on:** Member 2 for the data model, and Member 4 for the app shell.

**Others need from you:** the snapshot by hour 8.

**Done when:** at least 30 size-level categories have products from both stores, and lists, import and cards work on a phone.

## Member 2: Backend lead

**Goal:** a stable API, and a cart that gives correct plans. You also own integration.

**Before the event**
- [ ] Install PostgreSQL 16+, and write the shared setup notes.
- [ ] Choose the demo city with the team.
- [ ] Install `cloudflared`, and prepare the HTTPS demo setup.

**During the event**
- [ ] Task 1: build the skeleton, database and test fixtures.
- [ ] Task 6: add login and the demo user.
- [ ] Task 7: add the catalog and store selection.
- [ ] Task 3: build the optimiser, with every listed test case.
- [ ] Task 8: add shopping lists.
- [ ] Task 9: add plans, the one-time suggestion and directions.
- [ ] Task 13: add the wallet, simulated rewards and the cards API.
- [ ] Connect all screens to the real API, and fix integration bugs.
- [ ] Task 19: write the full-loop test, and run the app on a phone over HTTPS.

**Depends on:** Member 1 for real data, though tests can use sample data until then.

**Others need from you:** the API contract by hour 2, and the skeleton before anyone else starts backend work.

**Done when:** the full-loop test passes, and a phone can run the app over HTTPS.

## Member 3: Scanning and points

**Goal:** a real receipt turns into correct points, and a plan turns into a list. This is the riskiest part of the project, so it starts early.

**Before the event**
- [ ] Install Tesseract with Romanian data, and confirm `tesseract --list-langs` shows `ron`.
- [ ] Photograph 5 real receipts each from Auchan and Carrefour.
- [ ] Buy 5 products at Auchan, and compare the receipt with the online prices.
- [ ] Prepare a PDF, a picture and a copied text message of a nutrition plan.

**During the event**
- [ ] Task 2: build the points calculation.
- [ ] Task 10, step 1: test OCR on real receipts, and tell the team the result by hour 8.
- [ ] Task 10: build the local reader, parsers, abbreviation dictionary and fuzzy matching.
- [ ] Task 11: add the receipt upload, checks, matching and points award.
- [ ] Task 12: add list import for all three input types.
- [ ] Tune the match score and per-store rules on real receipts.
- [ ] Task 19: record the accuracy results, and prepare the demo receipt.

**Depends on:** Member 2 for the data model and for activated lists (Task 9). Until Task 9 is ready, test with fixtures.

**Others need from you:** the OCR result by hour 8, because it decides whether to switch to RapidOCR.

**Done when:** the demo receipt gives the expected points every time, and all three import types build a list.

## Member 4: Frontend lead and pitch

**Goal:** the main demo flow feels smooth on a phone, and the pitch is ready.

**Before the event**
- [ ] Install Node.js and the Angular CLI.
- [ ] Sketch the main screens, and agree the bottom navigation.
- [ ] Draft the pitch: the problem, the demo and why it's different.

**During the event**
- [ ] Task 14: build the PWA shell, login, settings and Romanian text file.
- [ ] Task 15: build the browse, cart and plan screens, using mock data until the API is ready.
- [ ] Task 17: build the receipt and wallet screens.
- [ ] Polish the phone layout, the loading states and the error messages.
- [ ] Task 19: write the demo script, record the backup video, and lead the rehearsal.

**Depends on:** Member 2 for the API. Use its `/docs` page and mock data until each route is ready.

**Others need from you:** the app shell by hour 6, so Member 1 can add screens.

**Done when:** a first-time viewer can follow the full loop on a phone without explanation.

## Working rules

- Agree the API in hours 0–2, and don't change a route without telling the frontend members.
- Use one branch per task, and merge to `main` only when its tests pass. Frontend tasks merge into the `frontend` branch instead, and `frontend` merges to `main` when all of it is ready.
- Keep UI text in `frontend/src/app/shared/ro.ts` and `en.ts`, and add every string to both.
- Keep `.env`, secrets and raw scrape output out of git.
- After hour 21, fix bugs only.
- If you're stuck for 30 minutes, tell the team.
- Write each task's tests first, watch them fail, then make them pass.

## Task details

Each task lists its files, what other tasks rely on, the decisions already made, and the tests that prove it works.

### Task 1: Project skeleton and database (Member 2)

- **Files:** `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `backend/app/{__init__,config,db,models,textutil,main}.py`, `tests/conftest.py`
- **Setup:** require Python `>=3.12,<3.13`, and make both `app` and `dealdata` importable under `uv run` and pytest. `.gitignore` covers `.env`, `.venv`, `data/raw/`, `node_modules` and `frontend/dist`.
- **Produces:** `get_settings() -> Settings`, `get_db()`, all models in `app.models`, `fold(text: str) -> str`, `app.main.app`
- **Test fixtures:** `db` (connects to the one `dealdirection` database through `DATABASE_URL` and rolls back a transaction after each test), `client`, and `sample` (2 stores, `Lapte → 3.5% → 1 l`, 3 products)
- **Tests:**
  - Settings match the README's configuration table.
  - `fold("Brânză de Țară") == "branza de tara"`.
  - `GET /api/health` returns `{"status": "ok"}`.
  - A repeated receipt fingerprint raises `IntegrityError`.

### Task 2: Points calculation (Member 3)

- **Files:** `backend/app/points/logic.py`, `tests/backend/test_points.py`
- **Produces:** `calculate_points(estimate: Decimal, paid: Decimal, margin: Decimal, max_modifier: Decimal, points_per_lei: int) -> PointsResult`, a frozen dataclass with `estimate, paid, diff, modifier, points`
- **Rule:** `diff = (paid - estimate) / estimate`. If `diff < margin`, the modifier is 1.00. Otherwise it's `min(1 + diff, max_modifier)`. Points are `round(estimate × points_per_lei × modifier)`, rounding half up.
- **Tests:** a zero estimate raises `ValueError`, and at 100 lei estimate and 10 points per lei:

| Paid | Modifier | Points |
|---|---|---|
| 90 | 1.00 | 1,000 |
| 103 | 1.00 | 1,000 |
| 105 | 1.05 | 1,050 |
| 112 | 1.12 | 1,120 |
| 140 | 1.25 | 1,250 |

### Task 3: Cart optimiser (Member 2)

- **Files:** `backend/app/optimizer/logic.py`, `tests/backend/test_optimizer.py`
- **Produces frozen dataclasses:**
  - `Item(id, size_category_id, quantity: Decimal, brand: str | None)`
  - `Offer(product_id, store_id, size_category_id, type_category_id, brand, name, price: Decimal)`
  - `Assignment(item_id, store_id, offer: Offer, line_total: Decimal)`
  - `Plan(kind: Literal["single", "split"], total: Decimal, assignments: tuple[Assignment, ...])`
  - `Missing(item_id, store_id, options: tuple[Offer, ...])`
  - `Resolution(item_id, store_id, replacement: Offer | None)`
  - `PlanResult(single, split, split_saving: Decimal, missing, unavailable: tuple[int, ...])`
  - `Suggestion(store_id, saving: Decimal)`
- **Produces functions:**
  - `build_plans(items, offers, store_ids, min_split_saving, resolutions=()) -> PlanResult`
  - `find_suggestion(items, offers, selected_ids, unselected_ids) -> Suggestion | None`
- **Algorithm:**
  1. An item matches an offer on `size_category_id`, and on brand if the item has one (ignoring case).
  2. Items with no matching offer at any selected store go in `unavailable`, and leave all totals.
  3. For each selected store, apply its resolutions, then count items still missing.
  4. The single store has the fewest missing items, then the lowest total, then the lowest id.
  5. `missing` covers the single store only, and its options are that store's offers of the same type.
  6. In the split, each available item takes its cheapest offer at any selected store.
  7. `split_saving` is the single total minus the split's total over items still in the single plan.
  8. Return the split only if it uses 2+ stores, nothing is missing, and `split_saving >= min_split_saving`.
  9. `find_suggestion` compares the split total with each unselected store added, and returns the largest positive saving.
- **Tests:**
  - An empty cart or no stores gives no plans.
  - The single store has the lowest total.
  - A saving of exactly 10 shows the split, and 9.99 hides it.
  - A split using one store is hidden.
  - Unselected stores never appear.
  - Quantity multiplies price.
  - Brand items only appear at stores with that brand.
  - Items available nowhere are in `unavailable`.
  - Fewest missing beats a lower total.
  - `missing` lists same-type options at that store.
  - A replacement updates the total.
  - A `None` resolution removes the item from the single plan only.
  - The suggestion picks the largest saving, and is `None` with no saving.

### Task 4: Product normalisation and category tree (Member 1)

- **Files:** `data/dealdata/normalize.py`, `data/dealdata/tree.py`, `data/tree.yaml`, `tests/data/test_normalize.py`
- **Produces:**
  - `RawProduct(store, name, brand, barcode, price: Decimal, image_url, source_url)`
  - `Size(amount: Decimal, unit: str)`
  - `parse_size(name: str) -> Size | None`
  - `LeafRule(path: tuple[str, str, str], include, exclude, size: Size, aliases)`
  - `load_tree(path: Path) -> list[LeafRule]`
  - `classify(product: RawProduct, size: Size, rules: list[LeafRule]) -> LeafRule | None`
- **Rule:** `classify` compares folded text. Every `include` word must appear, no `exclude` word may appear, and the size must equal the leaf's size. Adjust the tree after the first scrape, because each leaf needs products at 2+ stores.
- **Tests:**
  - `1 l` → 1 l, `500 ml` → 0.5 l, `1,5kg` → 1.5 kg, `200g` → 0.2 kg, `6x0.5l` → 3 l, `10 buc` → 10 buc.
  - `Paine alba` has no size.
  - `Lapte de curatare Pouce, 300ml` isn't classified.
  - `Lapte integral Albalact, 3.5% grasime, 1 l` becomes `("Lapte", "3.5%", "1 l")`.
  - The real tree has 25–35 categories.

### Task 5: Scrapers and data load (Member 1)

- **Files:** `data/dealdata/{scrape_auchan,scrape_carrefour,scrape,load}.py`, `data/stores.yaml`, `data/snapshot/products.json`, `tests/data/`, `tests/fixtures/{auchan_search.json,carrefour_category.html}`
- **Produces:**
  - `parse_auchan(payload: list[dict]) -> list[RawProduct]`
  - `parse_carrefour(html: str, source_url: str) -> list[RawProduct]`
  - `load_snapshot(db, products: list[dict], stores: dict) -> None`
  - `uv run python -m dealdata.scrape` and `uv run python -m dealdata.load`
- **Rules:**
  - Save one small real response from each store as a fixture first.
  - Save `data/raw/` before parsing, so parser fixes don't need a re-scrape.
  - `load_snapshot` upserts on `(store_id, name)`, fills `search_text` with `fold(name + brand)`, and sets `updated_at` from the scrape date.
  - `stores.yaml` holds each store's colour and 2–3 locations in the demo city.
- **Tests:**
  - Both parsers read the real fixtures, with expected values taken from them.
  - Out-of-stock Auchan products are skipped.
  - Running the load twice doesn't duplicate rows, and the demo user exists.
- **Done when:** the snapshot has 150–300 products across both stores, and at least 30 leaves have products at both. If a site blocks the scrape, stop and tell the team.

### Task 6: Login (Member 2)

- **Files:** `backend/app/auth/router.py`, `backend/app/deps.py`, `tests/backend/test_auth.py`
- **Produces:** the login routes, each returning `{token}`, and the `current_user` dependency
- **Test fixtures:** `auth_client`, `other_client`, `demo_user`
- **Rules:** hash with bcrypt. Tokens are HS256 JWTs that expire after 7 days. The login error doesn't say which field was wrong.
- **Tests:**
  - Register then log in.
  - New users have all stores selected.
  - A duplicate email gives 409.
  - A password under 6 characters, or without a digit and a special character, gives 422.
  - A wrong password gives 401.
  - Demo login needs no details.
  - A bad token gives 401.

### Task 7: Catalog and store selection (Member 2)

- **Files:** `backend/app/catalog/router.py`, `tests/backend/test_catalog.py`
- **Produces:** the Stores and Catalog routes. `Product` is `{id, store_id, store_name, name, brand, price, image_url, updated_at}`. `GET /categories/{id}/products` returns `{generic, products}`, and `GET /search` returns `[{size_category_id, path, generic}]`.
- **Rule:** search compares `fold(q)` with `search_text` using `ILIKE`.
- **Tests:**
  - The tree walks category → type → size.
  - The generic option is the lowest price at selected stores.
  - Unselected stores never appear.
  - Brand search filters products.
  - `branza` finds `Brânză telemea`.
  - Prices include their update date.
  - No selected stores gives a null generic.
  - An unknown store id gives 422.

### Task 8: Shopping lists (Member 2)

- **Files:** `backend/app/lists/router.py`, `tests/backend/test_lists.py`
- **Produces:** the Lists and List items routes. Items are added with `{size_category_id, quantity, chosen_product_id?}`.
- **Rules:** `DELETE /lists/{id}` sets `deleted_at` and never removes the row. Normal list routes skip lists with `deleted_at` set. The trash shows lists deleted within `TRASH_RETENTION_DAYS`, and can restore them by clearing `deleted_at`. The trash routes aren't in the API table yet, so agree them with the frontend members.
- **Tests:**
  - Create, read, update and delete work.
  - Generic and brand items can be added, with the brand copied from the chosen product.
  - Adding the same item twice adds the quantity.
  - Zero quantity gives 422.
  - Another user's list gives 404.
  - Items are locked with a 409 once active, but renaming still works.
  - `complete` sets the state.

### Task 9: Plans, suggestion and directions (Member 2)

- **Files:** `backend/app/plans/router.py`, `backend/app/plans/geo.py`, `tests/backend/test_plans.py`
- **Produces:**
  - `POST /lists/{id}/plans {resolutions: [{item_id, store_id, replacement_product_id | null}]}` returns `{single, split, split_saving, missing, unavailable, suggestion}`
  - `POST /lists/{id}/activate {kind, resolutions}`
  - `GET /lists/{id}/parts` returns `[{store_id, store_name, items, estimate, receipt_done}]`
  - `GET /stores/{id}/directions` returns `{address, maps_url}`
  - `nearest(locations, lat: float, lng: float) -> StoreLocation`, using haversine distance
- **Rules:**
  - The stores used are the client's selection plus the list's `extra_store_id`.
  - Set `suggestion_shown` in the same request that returns a suggestion.
  - `activate` stores each item's store, product and estimated price, marks removed items, and sets the list to `active`.
  - `maps_url` is `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>`.
- **Tests:**
  - An empty list or no selected stores gives null plans.
  - The suggestion appears only once.
  - Accepting it adds the store to that list only.
  - Activating fixes the store, price and state.
  - Unresolved missing items give 409.
  - Activating an unavailable split gives 409.
  - A later catalog change doesn't affect an active list.
  - Directions use the nearest location, or the default without one.

### Task 10: Local document reader (Member 3)

- **Files:** `backend/app/documents/{schemas,ocr,receipt_parser,food_parser,fuzzy,reader}.py`, `data/abbreviations.yaml`, `tests/backend/test_documents.py`, `tests/backend/test_parsers.py`, `tests/fixtures/receipts/`
- **Produces models:**
  - `ReceiptLine(raw_text, quantity: Decimal, line_total: Decimal)`
  - `ReceiptData(store_name, purchased_at: datetime | None, total: Decimal | None, lines)`
  - `Food(name, amount: Decimal, unit: str, per_day: bool)`
  - `FoodList(plan_days: int | None, foods)`
  - `LineMatch(line_index: int, item_id: int)`
  - `FoodMapping(food_name, size_category_id: int | None)`
- **Produces functions:**
  - `image_to_text(content: bytes, settings) -> str` and `pdf_to_text(content: bytes, settings) -> str` in `ocr.py`, the only file that knows the OCR engine
  - `parse_receipt(text: str) -> ReceiptData`
  - `parse_foods(text: str) -> FoodList`
  - `score_line(line, item: dict, abbreviations: dict) -> float`
  - `DocumentError(Exception)`
- **Produces the reader:**
  - `DocumentReader` protocol with `read_receipt(content, media_type) -> ReceiptData`, `read_foods(content, media_type) -> FoodList`, `match_lines(lines, items) -> list[LineMatch]`, `map_foods(foods, leaves) -> list[FoodMapping]`
  - `items` dicts hold `id, name, brand, expected_price`, and `leaves` dicts hold `id, path, aliases`
  - `LocalDocumentReader(settings, abbreviations)`, `get_document_reader()`, and a `fake_reader` test fixture used by Tasks 11, 12 and 19
- **First step, time-boxed to 2 hours:** run real photos through Tesseract with `--psm 4` and `--psm 6`. Record the total, date, readable lines and time. If under about 80% of item lines are readable, try RapidOCR and tell the team. Save the text of 3 real receipts per store as fixtures, without personal data.
- **Rules:**
  - `ocr.py` finds and straightens the receipt, converts to greyscale, enlarges about 2x, applies adaptive thresholding, and gives `pytesseract` a 30-second timeout. Images stay in memory.
  - `pdf_to_text` uses `pypdf`, and renders pages with `pypdfium2` for OCR if there's no text layer.
  - `receipt_parser.py` uses shared date, total and quantity patterns, with small per-store rules based on real fixtures.
  - `food_parser.py` finds `<amount><unit> [de] <food>`, treats `zilnic` and `pe zi` as daily, and `<n> zile` as the plan length.
  - `fuzzy.py` folds text, expands abbreviations, then scores `0.7 × token_set_ratio + 0.3 × price closeness`.
  - Price closeness is `100 × max(0, 1 - |line_total/quantity - expected_price| / expected_price)`.
  - `match_lines` takes the highest scores first, uses each line and item once, and stops below `OCR_MIN_MATCH_SCORE`.
  - A brand item also needs `partial_ratio >= 80` on its brand.
- **Tests:**
  - Real receipt fixtures give the right store, total and date.
  - `0,734 KG x 7,99` gives quantity 0.734.
  - A missing total is `None`, with no crash.
  - `200g piept de pui zilnic` gives `("piept de pui", 200, "g", True)`.
  - `Plan 7 zile` gives `plan_days == 7`.
  - A closer price scores higher.
  - An abbreviation like `LAPTE ALB` scores over 70 against milk.
  - Each line and item is used once.
  - Low scores are ignored.
  - A brand item rejects another brand.
  - `map_foods` uses aliases, and unknown foods have no category.
  - A PDF with text skips OCR.
  - A generated `TOTAL 123.45` image is read, skipped if Tesseract isn't installed.
  - Bad bytes or a timeout raise `DocumentError`.

### Task 11: Receipt scan and points award (Member 3)

- **Files:** `backend/app/receipts/matching.py`, `backend/app/receipts/router.py`, `tests/backend/test_receipts.py`
- **Produces:**
  - `fingerprint(store_id: int, purchased_at: datetime, total: Decimal) -> str` (SHA-256)
  - `score_matches(matches, lines, items) -> tuple[Decimal, Decimal, list[MatchedLine]]`, returning estimate, paid and matched lines
  - `POST /lists/{id}/receipts?store_id=` (multipart) returning `{matched, unmatched_items, estimate, paid, modifier, points}`
- **Test fixtures:** `active_list` (one store) and `split_list` (two stores)
- **Route steps:**
  1. Check the list is active, the store has a part, and the file is allowed. Allow `image/jpeg`, `image/png` and `image/webp`, up to `MAX_UPLOAD_MB`.
  2. Run `read_receipt`, and reject it if the date, total or lines are missing.
  3. Reject it if the store's folded name doesn't contain the receipt's folded store name.
  4. Run `match_lines` on that part's items, ignoring unknown ids and repeats.
  5. If nothing matched, reject without saving.
  6. For each match, `qty = min(list qty, receipt qty)`, `estimate += estimated_price × qty`, and `paid += (line_total / receipt qty) × qty`.
  7. Run `calculate_points`, then save the receipt, lines and ledger entry in one transaction. An `IntegrityError` rolls back and returns 409.
  8. If every part now has a receipt, set the list to `completed`.
- **Tests:**
  - Matched items earn points and a ledger entry.
  - Extra lines and missing items earn nothing.
  - Paying 12% over gives x1.12.
  - A split list needs one receipt per store, and the second completes it.
  - The same receipt on another account gives 409.
  - A second receipt for the same part gives 409, with no extra points.
  - A simultaneous duplicate returns 409, and adds points once.
  - 1 kg listed with 0.734 kg bought gives estimate and paid of 7.34 at 10 lei/kg.
  - 1 pack listed with 5 packs bought at 5 lei each gives estimate and paid of 5.
  - The wrong store gives 422, naming the expected store.
  - An unreadable receipt gives 422, saves nothing, and can be retried.
  - No matches gives 422, and the fingerprint stays free.
  - A draft list gives 409.
  - An oversized file gives 413, and a wrong type gives 415.

### Task 12: List import (Member 3)

- **Files:** `backend/app/imports/mapping.py`, `backend/app/imports/router.py`, `tests/backend/test_imports.py`
- **Produces:**
  - `scale_foods(food_list: FoodList, days: int) -> list[ScaledFood]`, with `ScaledFood(name, amount: Decimal, unit)`
  - `packs_needed(amount, unit, leaf_amount, leaf_unit) -> int | None`
  - `POST /imports` (multipart: `days`, and one of `file` or `text`) returning `{items: [{food, size_category_id, path, packs}], unmapped: [food]}`
  - `POST /imports/confirm {name, items: [{size_category_id, packs}]}` returning `{list_id}`
- **Rules:**
  - `g` and `ml` convert to `kg` and `l`.
  - Daily foods multiply by `days`. Other foods multiply by `days / plan_days` when `plan_days` is known, and stay unchanged when it isn't.
  - A food with incompatible units goes to `unmapped`.
  - File rules match Task 11, plus `application/pdf`.
  - Pass `map_foods` only size-level categories.
- **Tests:**
  - 200 g daily for 7 days gives 1.4 kg.
  - A 7-day plan over 14 days doubles.
  - Repeated foods are added up.
  - `packs_needed(1.4, "kg", 1, "kg") == 2`.
  - `kg` against `l` gives `None`.
  - PDF, image and text each return a preview.
  - Both or neither input gives 422.
  - Days must be positive.
  - Unmapped foods are flagged.
  - Nothing usable gives 422.
  - A reader failure gives 422.
  - Confirming creates a draft list.

### Task 13: Wallet, rewards and cards (Member 2)

- **Files:** `backend/app/wallet/router.py`, `backend/app/wallet/rewards.py`, `backend/app/cards/router.py`, `tests/backend/test_wallet.py`, `tests/backend/test_cards.py`
- **Produces:** the Wallet and Cards routes. `GET /wallet` returns `{balance, history: [{amount, reason, created_at}]}`. `GET /rewards` returns `[{id, name, cost, store_name}]` from a static list labelled as sample data. `POST /rewards/{id}/redeem` returns the new voucher, `{id, code, reward_name, store_name, expires_at}`, and `GET /vouchers` returns the unused, unexpired ones.
- **Rules:** `redeem` locks the user row with `SELECT ... FOR UPDATE` before checking the balance, so two taps can't overspend. Card images use the same size limit as receipts.
- **Tests:**
  - The balance is the ledger's sum.
  - Redeeming adds a negative entry.
  - Too few points gives 409.
  - An unknown reward gives 404.
  - A card image round-trips.
  - A new card replaces the old one for that store.
  - Another user's card gives 404.
  - A non-image gives 415.

### Task 14: Frontend shell, login and settings (Member 4)

- **Files:** `frontend/` from `ng new frontend --routing --style=scss --ssr=false` and `ng add @angular/pwa`, `src/app/core/`, `src/app/shared/ro.ts`, `src/app/login/`, `src/app/settings/`, `proxy.conf.json`. Also update `backend/app/main.py`.
- **Produces:** `ApiService` with one typed method per route, `AuthService.token`, the bottom navigation (Home, Cart, Cards, from left to right), and `formatLei(value: string): string`. Home opens the Browse screen, and its seasonal offers box opens `/deals`. Lists, Import, Wallet and Settings are in the hamburger menu, and the account icon opens Settings.
- **Rules:** keep the token in `localStorage`. Settings has store toggles and logout. FastAPI serves `frontend/dist/frontend/browser`, and returns `index.html` for unknown non-API paths. Design for phone width first.
- **Tests:**
  - The token is stored after login, and sent on API calls.
  - A 401 logs out and redirects.
  - The demo button calls `/api/auth/demo`.
  - `formatLei('12.50')` gives `12,50 lei`.
  - Unknown paths serve `index.html`, while unknown API paths stay 404.

### Task 15: Browse, cart and plan screens (Member 4)

- **Files:** `frontend/src/app/{browse,cart,plan}/`
- **Produces:** routes `/browse`, `/cart/:listId` and `/plan/:listId`, and `CartService.currentListId`, which creates a draft list on first add
- **Rules:**
  - The cart replays the collected `resolutions` on each `/plans` call.
  - Choosing a plan calls `/activate`, then opens the plan screen.
  - Directions ask for the browser's location, and call the route without it if denied.
- **Tests:**
  - The generic price, store and update date are shown.
  - The generic option is added to the current list.
  - Both plans and the saving are shown when a split exists.
  - The app explains when splitting isn't worth it.
  - Missing items are asked about one at a time, and totals refresh.
  - The suggestion has accept and dismiss.
  - An empty cart or no stores shows a message.
  - The directions button opens `maps_url`.

### Task 16: Lists and import screens (Member 1)

- **Files:** `frontend/src/app/{lists,import}/`
- **Produces:** routes `/lists` and `/import`
- **Rules:** the single import button accepts a PDF or image file, or pasted text. Show a progress state while it reads.
- **Tests:**
  - Lists can be shown, renamed and deleted.
  - A draft list opens in the cart, and an active list opens its plan.
  - One of file or text is sent, with the number of days.
  - Mapped items are shown, and unmapped foods flagged.
  - Unmapped foods can be picked or removed before confirming.
  - The new list opens after confirming.
  - A failed import shows a retry message.

### Task 17: Receipt and wallet screens (Member 4)

- **Files:** `frontend/src/app/{receipt,wallet}/`
- **Produces:** routes `/receipt/:listId/:storeId` and `/wallet`
- **Rule:** use `<input type="file" accept="image/*" capture="environment">`, which opens the camera on phones and falls back to a file picker elsewhere.
- **Tests:**
  - The chosen photo uploads for that store.
  - The button is disabled while uploading, so a double tap sends once.
  - Matched items, unmatched items, estimate, paid, modifier and points are shown.
  - A wrong-store error shows the expected store.
  - An unreadable receipt asks for a retake.
  - A used receipt shows a clear message.
  - The wallet shows the balance and history.
  - Rewards are marked as simulated, and those over the balance are blocked.

### Task 18: Card wallet screen (Member 1)

- **Files:** `frontend/src/app/cards/`
- **Produces:** route `/cards`
- **Rules:** use cropperjs to crop in the browser, and upload a PNG. The generic card is a CSS design in the store's colour, with the store name and the code image.
- **Tests:**
  - Each card shows its store name and colour.
  - The cropped image uploads for the chosen store.
  - A card opens with the code large on a white background.
  - A card can be deleted after confirming.

### Task 19: Demo readiness (Everyone)

- **Files:** `tests/backend/test_demo_loop.py`, and any fixes to `README.md`
- **Steps:**
  1. Write `test_full_demo_loop`: demo login, confirm an import, get plans, activate a split, get directions, scan one receipt per store, and check the wallet equals both results combined.
  2. Run `uv run pytest`, `npx ng test --watch=false` and `npx ng build`.
  3. Build the frontend, load the data, and run `uv run uvicorn app.main:app --app-dir backend --port 8000`.
  4. Run `cloudflared tunnel --url http://localhost:8000`. The phone should open the HTTPS address, install the PWA and open the camera.
  5. Do the real-world checks in the README, and record the results in this file.
  6. Write the demo script, prepare the demo user's data from `data/demo_list.yaml`, and record a backup video.
- **Done when:** the full loop works on the phone with the real receipt.
