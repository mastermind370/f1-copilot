/** Tax season mode runs February through April (local time). */
export function isTaxSeason(d: Date): boolean {
  const m = d.getMonth();
  return m >= 1 && m <= 3;
}
