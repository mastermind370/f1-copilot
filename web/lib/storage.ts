// Personal facts live ONLY in this browser's localStorage.
// They are sent to the local API to compute the timeline and are never stored server-side.
// Storage can be unavailable (private mode, disabled storage), so every access is guarded.

import type { Facts } from "./api";

const KEY = "f1copilot.facts.v1";

export function loadFacts(): Facts {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Facts) : {};
  } catch {
    return {};
  }
}

export function saveFacts(facts: Facts): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(facts));
    return true;
  } catch {
    return false;
  }
}

export function clearFacts(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing stored */
  }
}
