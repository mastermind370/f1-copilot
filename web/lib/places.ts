// Client for the live listings proxy (/api/places). The API key lives only on the server.

import { API_URL } from "./api";

export interface PlacePhoto {
  name: string;
  attributions: { name: string; uri: string }[];
}

export interface Place {
  id: string;
  name: string;
  address: string;
  rating: number | null;
  ratingCount: number | null;
  priceLevel: number | null;
  type: string;
  summary: string;
  mapsUrl: string;
  openNow: boolean | null;
  photo: PlacePhoto | null;
  // OpenStreetMap extras (absent for Google results)
  cuisine?: string[];
  diet?: string[];
  hours?: string;
  website?: string;
  distanceKm?: number;
  osmUrl?: string;
}

export interface Attribution {
  text: string;
  url: string;
}

export interface PlacesResult {
  places: Place[];
  attribution: Attribution;
}

export type PlacesErrorCode = "places_not_configured" | "places_daily_limit" | "places_upstream" | "places_invalid" | "offline";

export class PlacesError extends Error {
  constructor(public code: PlacesErrorCode) {
    super(code);
  }
}

/** Google's language codes for the app's languages. */
export const PLACES_LANG: Record<string, string> = { en: "en", zh: "zh-CN", hi: "hi", ko: "ko", vi: "vi", es: "es", bn: "bn" };

export async function fetchPlaces(category: string, near: string, lang: string, signal?: AbortSignal): Promise<PlacesResult> {
  const qs = new URLSearchParams({ category, near, lang: PLACES_LANG[lang] ?? "en" });
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/places?${qs}`, { signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new PlacesError("offline");
  }
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new PlacesError(typeof detail === "string" && detail.startsWith("places_") ? (detail as PlacesErrorCode) : "places_upstream");
  }
  return (await res.json()) as PlacesResult;
}

export function photoUrl(name: string): string {
  return `${API_URL}/api/places/photo?${new URLSearchParams({ name })}`;
}

/** Five star slots for a 0–5 rating, rounded to the nearest half star. */
export function starSlots(rating: number): ("full" | "half" | "empty")[] {
  const halves = Math.round(Math.min(5, Math.max(0, rating)) * 2);
  return Array.from({ length: 5 }, (_, i) => (halves >= (i + 1) * 2 ? "full" : halves === i * 2 + 1 ? "half" : "empty"));
}

export function priceLabel(level: number | null): string {
  return level && level > 0 ? "$".repeat(Math.min(4, level)) : "";
}

/** 812 -> "812", 1530 -> "1.5K", 12400 -> "12K" */
export function compactCount(n: number, locale: string): string {
  return new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/** Kilometres to a short US distance label: "0.3 mi", "2 mi". */
export function miles(km: number): string {
  const mi = km * 0.621371;
  return mi < 10 ? `${mi.toFixed(1)} mi` : `${Math.round(mi)} mi`;
}
