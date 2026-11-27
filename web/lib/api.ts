// Typed client for the local Copilot API (`copilot serve`).

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface Citation {
  chunk_id: string;
  url: string;
  heading: string;
  text: string;
  retrieved_at: string;
  source: string;
}

export interface AskResponse {
  question: string;
  text: string;
  refused: boolean;
  reason: string | null;
  confidence: number;
  citations: Citation[];
  cached: boolean;
  disclaimer: string;
}

export type FactType = "date" | "bool" | "int" | "str";

export interface FactField {
  name: string;
  type: FactType;
  label: string;
  help: string;
  options?: string[];
}

export type ItemKind = "deadline" | "earliest" | "window" | "limit" | "notice";
export type ItemStatus = "upcoming" | "active" | "past" | "info";

export interface TimelineItem {
  rule_id: string;
  rule_version: number;
  title: string;
  kind: ItemKind;
  label: string;
  status: ItemStatus;
  explanation: string[];
  source_url: string;
  verification: "primary" | "secondary";
  last_verified: string;
  citation: string | null;
  date: string | null;
  start: string | null;
  end: string | null;
  value: number | null;
  unit: string | null;
  message: string | null;
  days_until: number | null;
  notes: string[];
}

export interface Timeline {
  as_of: string;
  items: TimelineItem[];
  needs_info: { rule_id: string; title: string; missing: string[] }[];
  not_applicable: string[];
  not_in_effect: string[];
  stale_rules: string[];
  disclaimer: string;
}

export interface RuleInfo {
  id: string;
  version: number;
  title: string;
  category: string;
  summary: string;
  source_url: string;
  citation: string | null;
  verification: "primary" | "secondary";
  last_verified: string;
  stale: boolean;
  notes: string[];
}

export interface ChangeReport {
  checked_at: string;
  baseline: string;
  has_content_changes: boolean;
  changed: { url: string }[];
  new: { url: string }[];
  unreachable: string[];
  rules_to_reverify: { rule_id: string; source_url: string; reason: string }[];
  stale_answers: number;
}

export type FactValue = string | number | boolean;
export type Facts = Record<string, FactValue>;

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Can't reach the Copilot API at ${API_URL}. Start it with \`copilot serve\`.`,
      0,
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = "Invalid request";
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  ask: (question: string) =>
    request<AskResponse>("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
  timeline: (facts: Facts, asOf?: string) =>
    request<Timeline>("/api/timeline", {
      method: "POST",
      body: JSON.stringify({ facts, as_of: asOf || null }),
    }),
  factsSchema: () => request<FactField[]>("/api/facts-schema"),
  rules: () => request<RuleInfo[]>("/api/rules"),
  changes: () => request<{ report: ChangeReport | null }>("/api/changes"),
};

/** Format a YYYY-MM-DD date without timezone drift.
 *  new Date("2027-05-15") is UTC midnight, so formatting it in New York time would
 *  show May 14. Always format date-only values in UTC. */
export function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString(undefined, {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
