// Exact decimal maths for prices and quantities. Everything stays a string or a
// BigInt, because the project rule is that money never passes through a float.

// The backend's POINTS_PER_LEI. Change both together until an API route exposes it.
const POINTS_PER_LEI = 10n;

const PRICE_DECIMALS = 2;
const QUANTITY_DECIMALS = 3;

export function normalizeAmount(value: string): string {
  return value.trim().replace(',', '.');
}

export function isPrice(value: string): boolean {
  return /^\d{1,7}(\.\d{1,2})?$/.test(value);
}

export function isQuantity(value: string): boolean {
  return /^\d{1,5}(\.\d{1,3})?$/.test(value) && scaled(value, QUANTITY_DECIMALS) > 0n;
}

export function totalOf(lines: { price: string; quantity: string }[]): string {
  const exact = lines.reduce(
    (sum, line) =>
      sum + scaled(line.price, PRICE_DECIMALS) * scaled(line.quantity, QUANTITY_DECIMALS),
    0n,
  );
  return formatBani((exact + 500n) / 1000n);
}

export function compareAmounts(first: string, second: string): number {
  const difference = scaled(first, PRICE_DECIMALS) - scaled(second, PRICE_DECIMALS);
  return difference === 0n ? 0 : difference < 0n ? -1 : 1;
}

export function subtractAmounts(first: string, second: string): string {
  return formatBani(scaled(first, PRICE_DECIMALS) - scaled(second, PRICE_DECIMALS));
}

export function pointsFor(total: string): number {
  return Number((scaled(total, PRICE_DECIMALS) * POINTS_PER_LEI + 50n) / 100n);
}

export function addQuantities(first: string, second: string): string {
  return formatQuantity(scaled(first, QUANTITY_DECIMALS) + scaled(second, QUANTITY_DECIMALS));
}

// One less, or null when that leaves nothing.
export function decreaseQuantity(value: string): string | null {
  const remaining = scaled(value, QUANTITY_DECIMALS) - 1000n;
  return remaining > 0n ? formatQuantity(remaining) : null;
}

function formatQuantity(thousandths: bigint): string {
  const whole = thousandths / 1000n;
  const decimals = String(thousandths % 1000n)
    .padStart(QUANTITY_DECIMALS, '0')
    .replace(/0+$/, '');
  return decimals ? `${whole}.${decimals}` : `${whole}`;
}

function formatBani(bani: bigint): string {
  return `${bani / 100n}.${String(bani % 100n).padStart(2, '0')}`;
}

function scaled(value: string, decimals: number): bigint {
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole + fraction.padEnd(decimals, '0').slice(0, decimals));
}
