// Document expiry tracker: pure status logic, tested in documents.test.ts.

export const DOCS = ["passport", "visa", "i20", "ead", "signature"] as const;
export type DocId = (typeof DOCS)[number];

export type DocStatus = "missing" | "expired" | "soon" | "ok";

export const SOON_DAYS = 90;

export function docStatus(expiry: string | undefined, today: string): { status: DocStatus; days: number | null } {
  if (!expiry) return { status: "missing", days: null };
  const days = Math.round((Date.parse(`${expiry}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000);
  if (Number.isNaN(days)) return { status: "missing", days: null };
  if (days < 0) return { status: "expired", days };
  return { status: days <= SOON_DAYS ? "soon" : "ok", days };
}

/** Travel signatures are generally valid 12 months (6 months on OPT). */
export function signatureExpiry(signed: string, onOpt: boolean): string {
  const d = new Date(`${signed}T00:00:00Z`);
  const months = onOpt ? 6 : 12;
  const day = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + months);
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(day, last));
  return d.toISOString().slice(0, 10);
}
