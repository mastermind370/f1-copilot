// Outbound search links. The app never invents listings, stores or restaurants: it builds a
// live search on Google Maps or Google, scoped to the student's campus, and the results come
// from there. That keeps every school covered without stale or made-up data.

export function mapsSearch(query: string, near: string): string {
  return `https://www.google.com/maps/search/${encodeURIComponent(`${query} near ${near}`)}`;
}

export function mapsDirections(origin: string, destination: string, mode: "transit" | "driving" = "transit"): string {
  const p = new URLSearchParams({ api: "1", origin, destination, travelmode: mode });
  return `https://www.google.com/maps/dir/?${p.toString()}`;
}

export function siteSearch(query: string, domain: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(`${query} site:${domain}`)}`;
}
