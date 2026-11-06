// Money arrives from the API as a string, so this never converts it to a float.
export function formatLei(value: string): string {
  const [whole, decimals = ''] = value.split('.');
  return `${whole},${decimals.padEnd(2, '0').slice(0, 2)} lei`;
}
