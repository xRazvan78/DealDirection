// Money arrives from the API as a string, so this never converts it to a float.
export function formatLei(value: string): string {
  const [whole, decimals = ''] = value.split('.');
  return `${whole},${decimals.padEnd(2, '0').slice(0, 2)} lei`;
}

// "2.000" -> "2", "0.734" -> "0,734".
export function formatQuantity(value: string): string {
  const [whole, decimals = ''] = value.split('.');
  const kept = decimals.replace(/0+$/, '');
  return kept ? `${whole},${kept}` : whole;
}

// A receipt's printed date, kept as written: "2026-10-26T11:39:00" -> "26.10.2026 11:39".
// A receipt whose time wasn't read arrives as midnight, so midnight isn't shown.
export function formatReceiptDate(value: string): string {
  const [date, time = ''] = value.split('T');
  const day = date.split('-').reverse().join('.');
  const clock = time.slice(0, 5);
  return clock && clock !== '00:00' ? `${day} ${clock}` : day;
}

// A distance the backend rounded to one decimal, written the Romanian way: 0,8 km.
export function formatKm(km: number): string {
  return `${String(km).replace('.', ',')} km`;
}
