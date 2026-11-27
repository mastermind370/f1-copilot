"use client";

import { useEffect } from "react";

// Catches render errors on any page. If Plausible is loaded, it records an anonymous
// "Error" event with only the error's name (no message, stack, URL query or personal data).
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    const w = window as unknown as { plausible?: (e: string, o?: { props: Record<string, string> }) => void };
    w.plausible?.("Error", { props: { kind: error.name || "Error" } });
  }, [error]);
  return (
    <div className="page">
      <div className="card empty-card" role="alert">
        <h1>Something went wrong</h1>
        <p>This page hit an unexpected error. Your saved information is still on this device.</p>
        <button type="button" className="btn" onClick={reset}>Try again</button>
      </div>
    </div>
  );
}
