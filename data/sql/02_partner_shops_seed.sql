-- Coin shop partners and their gift cards. SAMPLE DATA: spending points is simulated.
-- Safe to re-run: existing rows are updated, never duplicated.
-- Cost: 100 points per leu, the same rate as the rewards in data/rewards.yaml.

INSERT INTO partner_shops (name, description, website, colour) VALUES
    ('Decathlon', 'Echipament și îmbrăcăminte sport', 'https://www.decathlon.ro', '#3643ba'),
    ('Delfino',   'Partener DealDirection',           NULL,                       '#0077b6'),
    ('SuperBob',  'Partener DealDirection',           NULL,                       '#e63946')
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    website     = EXCLUDED.website,
    colour      = EXCLUDED.colour,
    active      = true;

INSERT INTO partner_gift_cards (shop_id, name, value_lei, cost_points)
SELECT s.id, 'Card cadou ' || s.name || ' ' || v.value_lei || ' lei', v.value_lei, v.value_lei * 100
FROM partner_shops s
CROSS JOIN (VALUES (50), (100), (150)) AS v (value_lei)
WHERE s.name IN ('Decathlon', 'Delfino', 'SuperBob')
ON CONFLICT (shop_id, value_lei) DO UPDATE SET
    name        = EXCLUDED.name,
    cost_points = EXCLUDED.cost_points,
    active      = true;
