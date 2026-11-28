// Client for the visa-sponsor lookup (/api/employers).

import { API_URL } from "./api";

export interface EmployerHit {
  key: string;
  name: string;
  city: string;
  state: string;
  new_recent: number; // new-employment H-1B approvals in the last 3 fiscal years on file
  approved: number; // all approvals on file
  filings: number; // certified full-time H-1B salary filings (LCAs)
  medianWage: number | null;
}

export interface EmployerYear {
  fy: number;
  new_approved: number;
  new_denied: number;
  cont_approved: number;
  cont_denied: number;
}

export interface EmployerDetail {
  key: string;
  name: string;
  city: string;
  state: string;
  years: EmployerYear[];
  jobs: { title: string; filings: number; medianWage: number | null; low: number | null; high: number | null }[];
  filings: number;
  medianWage: number | null;
  states: { state: string; filings: number }[];
  lcaYears: number[];
  sources: { file: string; kind: string }[];
}

export class EmployersError extends Error {
  constructor(public code: "employers_not_loaded" | "employer_not_found" | "offline" | "error") {
    super(code);
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new EmployersError("offline");
  }
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new EmployersError(detail === "employers_not_loaded" || detail === "employer_not_found" ? detail : "error");
  }
  return (await res.json()) as T;
}

export const searchEmployers = (q: string, state: string, signal?: AbortSignal) =>
  get<{ results: EmployerHit[] }>(`/api/employers/search?${new URLSearchParams({ q, state })}`, signal).then((r) => r.results);

export const employerDetail = (key: string, signal?: AbortSignal) =>
  get<EmployerDetail>(`/api/employers/${encodeURIComponent(key)}`, signal);

/** 166400 -> "$166K" */
export function money(n: number | null, locale = "en-US"): string {
  if (n == null) return "—";
  return new Intl.NumberFormat(locale, { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: n >= 1_000_000 ? 1 : 0 }).format(n);
}

/** Share of new-employment petitions approved, or null when there were none. */
export function approvalRate(y: Pick<EmployerYear, "new_approved" | "new_denied">): number | null {
  const total = y.new_approved + y.new_denied;
  return total ? Math.round((y.new_approved / total) * 100) : null;
}
