-- Coin shop: partner shops where users spend their points, and their gift cards.
-- Safe to re-run: it only creates what is missing. Run with
--   uv run python -m dealdata.run_sql
-- or psql -f. Keep in step with PartnerShop and PartnerGiftCard in backend/app/models.py.
--
-- Rows are switched off (active = false), never deleted, because vouchers
-- redeemed later will point to them.

CREATE TABLE IF NOT EXISTS partner_shops (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(300),
    website     VARCHAR(300),
    colour      VARCHAR(7)   NOT NULL,
    logo        VARCHAR(500),
    active      BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE IF NOT EXISTS partner_gift_cards (
    id          SERIAL PRIMARY KEY,
    shop_id     INTEGER       NOT NULL REFERENCES partner_shops (id) ON DELETE RESTRICT,
    name        VARCHAR(200)  NOT NULL,
    value_lei   NUMERIC(10, 2) NOT NULL,
    cost_points INTEGER       NOT NULL,
    active      BOOLEAN       NOT NULL DEFAULT true,
    CONSTRAINT partner_gift_cards_shop_id_value_lei_key UNIQUE (shop_id, value_lei),
    CONSTRAINT value_positive CHECK (value_lei > 0),
    CONSTRAINT cost_positive CHECK (cost_points > 0)
);

CREATE INDEX IF NOT EXISTS ix_partner_gift_cards_shop_id ON partner_gift_cards (shop_id);
