import { Product } from '../core/models';
import { compareAmounts, subtractAmounts, totalOf } from '../shared/money';

// The backend's MIN_SPLIT_SAVING_LEI. This file follows the optimiser rules in
// Task 3 of TEAM_TASKS.md, and `/lists/{id}/plans` replaces it once that exists.
const MIN_SPLIT_SAVING_LEI = '10';

export interface PlanItem {
  id: number;
  quantity: string;
  sizeCategoryId?: number | null;
}

export interface PlanLine {
  itemId: number;
  offer: Product;
}

export interface CartPlan {
  total: string;
  lines: PlanLine[];
}

export interface SingleStorePlan extends CartPlan {
  storeName: string;
  missing: number;
}

export interface PlanComparison {
  single: SingleStorePlan;
  split: CartPlan | null;
  saving: string;
  unmatched: number;
}

type Offers = ReadonlyMap<number, Product[]>;

export function comparePlans(items: PlanItem[], offers: Offers): PlanComparison | null {
  const comparable = items.filter((item) => offersFor(item, offers).length > 0);
  if (!comparable.length) {
    return null;
  }

  const single = bestSingleStore(comparable, offers);
  const splitLines = comparable.map((item) => ({
    itemId: item.id,
    offer: cheapest(offersFor(item, offers)),
  }));
  const coveredBySingle = new Set(single.lines.map((line) => line.itemId));
  const saving = subtractAmounts(
    single.total,
    totalFor(splitLines.filter((line) => coveredBySingle.has(line.itemId)), comparable),
  );
  const usesSeveralStores = new Set(splitLines.map((line) => line.offer.store_id)).size > 1;
  const worthSplitting =
    usesSeveralStores && compareAmounts(saving, MIN_SPLIT_SAVING_LEI) >= 0;

  return {
    single,
    split: worthSplitting ? { total: totalFor(splitLines, comparable), lines: splitLines } : null,
    saving,
    unmatched: items.length - comparable.length,
  };
}

// Fewest missing items wins, then the lowest total, then the lowest store id.
function bestSingleStore(items: PlanItem[], offers: Offers): SingleStorePlan {
  const everyOffer = items.flatMap((item) => offersFor(item, offers));
  const storeIds = [...new Set(everyOffer.map((offer) => offer.store_id))].sort((a, b) => a - b);

  const plans = storeIds.map((storeId): SingleStorePlan => {
    const lines = items.flatMap((item): PlanLine[] => {
      const atStore = offersFor(item, offers).filter((offer) => offer.store_id === storeId);
      return atStore.length ? [{ itemId: item.id, offer: cheapest(atStore) }] : [];
    });
    return {
      storeName: everyOffer.find((offer) => offer.store_id === storeId)?.store_name ?? '',
      total: totalFor(lines, items),
      lines,
      missing: items.length - lines.length,
    };
  });

  return plans.reduce((best, plan) => {
    const fewerMissing = plan.missing < best.missing;
    const cheaper = plan.missing === best.missing && compareAmounts(plan.total, best.total) < 0;
    return fewerMissing || cheaper ? plan : best;
  });
}

function offersFor({ sizeCategoryId }: PlanItem, offers: Offers): Product[] {
  return (sizeCategoryId && offers.get(sizeCategoryId)) || [];
}

function cheapest(offers: Product[]): Product {
  return offers.reduce((best, offer) => {
    const order = compareAmounts(offer.price, best.price);
    return order < 0 || (order === 0 && offer.store_id < best.store_id) ? offer : best;
  });
}

function totalFor(lines: PlanLine[], items: PlanItem[]): string {
  return totalOf(
    lines.map(({ itemId, offer }) => ({
      price: offer.price,
      quantity: items.find((item) => item.id === itemId)?.quantity ?? '0',
    })),
  );
}
