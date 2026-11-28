"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ClockIcon, ExternalIcon, GlobeIcon, MapPinIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import type { MessageKey } from "@/lib/i18n";
import { type Attribution, compactCount, fetchPlaces, miles, type Place, PlacesError, photoUrl, priceLabel, starSlots } from "@/lib/places";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; places: Place[]; attribution: Attribution }
  | { kind: "error"; code: string };

function Stars({ rating }: { rating: number }) {
  return (
    <span className="stars" aria-hidden="true">
      {starSlots(rating).map((s, i) => <span key={i} className={`star ${s}`}>★</span>)}
    </span>
  );
}

function PlaceRow({ p, emoji }: { p: Place; emoji: string }) {
  const { t, locale } = usePrefs();
  const [imgOk, setImgOk] = useState(true);
  const credit = p.photo?.attributions[0];
  return (
    <li className="place">
      <div className={`place-photo ${p.photo && imgOk ? "" : "empty"}`}>
        {p.photo && imgOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photoUrl(p.photo.name)} alt="" loading="lazy" width={96} height={96} onError={() => setImgOk(false)} />
        ) : (
          <span className="place-photo-fallback" aria-hidden="true">{emoji}</span>
        )}
      </div>
      <div className="place-body">
        <h4 className="place-name">{p.name}</h4>
        <div className="place-meta">
          {p.rating != null && (
            <span className="place-rating"
              aria-label={t("places.ratingLabel", { rating: p.rating.toFixed(1), count: p.ratingCount ?? 0 })}>
              <strong>{p.rating.toFixed(1)}</strong>
              <Stars rating={p.rating} />
              {p.ratingCount != null && <span className="muted">({compactCount(p.ratingCount, locale)})</span>}
            </span>
          )}
          {priceLabel(p.priceLevel) && <span className="muted" aria-label={t("places.price")}>{priceLabel(p.priceLevel)}</span>}
          {p.type && <span className="muted">{p.type}</span>}
          {p.distanceKm != null && <span className="muted">{t("places.away", { d: miles(p.distanceKm) })}</span>}
          {p.openNow != null && (
            <span className={`open-badge ${p.openNow ? "open" : "closed"}`}>{t(p.openNow ? "places.open" : "places.closed")}</span>
          )}
        </div>
        {p.summary && <p className="place-summary">{p.summary}</p>}
        {((p.cuisine?.length ?? 0) > 0 || (p.diet?.length ?? 0) > 0) && (
          <div className="place-chips">
            {p.cuisine?.map((c) => <span key={c} className="chip">{c}</span>)}
            {p.diet?.map((d) => <span key={d} className="chip diet">{t(`places.diet.${d}` as MessageKey)}</span>)}
          </div>
        )}
        {p.hours && <p className="place-address muted small"><ClockIcon size={14} /> <span lang="en">{p.hours}</span></p>}
        {p.address && <p className="place-address muted small"><MapPinIcon size={14} /> {p.address}</p>}
        <div className="place-foot">
          {p.mapsUrl && (
            <a href={p.mapsUrl} target="_blank" rel="noreferrer" className="place-maps">
              {t("places.openMaps")} <ExternalIcon size={14} />
            </a>
          )}
          {p.website && (
            <a href={p.website} target="_blank" rel="noreferrer nofollow" className="place-maps">
              <GlobeIcon size={14} /> {t("places.website")}
            </a>
          )}
          {credit && (
            <span className="photo-credit muted">
              {t("places.photoBy")}{" "}
              {credit.uri ? <a href={credit.uri} target="_blank" rel="noreferrer">{credit.name}</a> : credit.name}
            </span>
          )}
        </div>
      </div>
    </li>
  );
}

/** A category tile that opens into live listings. Results load only when it's first opened. */
export default function PlaceDropdown({ category, emoji, mapsHref }: { category: MessageKey; emoji: string; mapsHref: string }) {
  const { t, school, lang } = usePrefs();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<State>({ kind: "idle" });
  const loadedFor = useRef("");
  const panelId = useId();

  useEffect(() => {
    if (!open || !school) return;
    const key = `${school.city}|${lang}`;
    if (loadedFor.current === key) return;
    const ctl = new AbortController();
    setState({ kind: "loading" });
    fetchPlaces(category, school.city, lang, ctl.signal)
      .then((r) => { loadedFor.current = key; setState({ kind: "ready", places: r.places, attribution: r.attribution }); })
      .catch((e) => { if (e.name !== "AbortError") setState({ kind: "error", code: e instanceof PlacesError ? e.code : "offline" }); });
    return () => ctl.abort();
  }, [open, school, lang, category]);

  const label = t(category);
  return (
    <div className={`place-dd ${open ? "is-open" : ""}`}>
      <button type="button" className="link-card place-trigger" aria-expanded={open} aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}>
        <span className="link-icon" aria-hidden="true">{emoji}</span>
        <span className="link-text"><span className="link-label">{label}</span></span>
        <span className="chev" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div id={panelId} className="place-panel" role="region" aria-label={label} aria-busy={state.kind === "loading"}>
          {state.kind === "loading" && (
            <ul className="place-list" aria-hidden="true">
              {[0, 1, 2].map((i) => <li key={i} className="place skeleton"><div className="place-photo" /><div className="place-body"><span /><span /></div></li>)}
            </ul>
          )}
          {state.kind === "ready" && state.places.length === 0 && <p className="muted">{t("places.none")}</p>}
          {state.kind === "ready" && state.places.length > 0 && state.attribution.url && (
            <p className="muted small osm-note">{t("places.osmNote")}</p>
          )}
          {state.kind === "ready" && state.places.length > 0 && (
            <ul className="place-list">{state.places.map((p) => <PlaceRow key={p.id} p={p} emoji={emoji} />)}</ul>
          )}
          {state.kind === "error" && (
            <p className="muted">{t(`places.err.${state.code}` as MessageKey)}</p>
          )}
          <div className="place-panel-foot">
            <a className="btn ghost small" href={mapsHref} target="_blank" rel="noreferrer">
              {t("places.seeAll")} <ExternalIcon size={14} />
            </a>
            {state.kind === "ready" && state.places.length > 0 && (
              <span className="muted small">
                {state.attribution.url
                  ? <a href={state.attribution.url} target="_blank" rel="noreferrer">{state.attribution.text}</a>
                  : t("places.attribution")}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
