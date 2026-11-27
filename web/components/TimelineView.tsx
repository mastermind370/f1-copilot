import type { FactField, Timeline, TimelineItem } from "@/lib/api";
import { formatDate } from "@/lib/api";

function when(item: TimelineItem): string {
  switch (item.kind) {
    case "window":
      return `${formatDate(item.start)} → ${formatDate(item.end)}`;
    case "deadline":
    case "earliest":
      return formatDate(item.date);
    case "limit":
      return `${item.value} ${item.unit}`;
    default:
      return "";
  }
}

function relative(item: TimelineItem): string | null {
  if (item.status === "active") return item.kind === "window" ? "Open now" : "Now";
  if (item.status === "upcoming" && item.days_until !== null) {
    return item.days_until === 0 ? "Today" : `In ${item.days_until} days`;
  }
  return null;
}

function ItemCard({ item }: { item: TimelineItem }) {
  const rel = relative(item);
  return (
    <article className={`card item status-${item.status}`}>
      <div className="item-head">
        <div>
          <h3>{item.label}</h3>
          <div className="when">{when(item)}</div>
        </div>
        {rel && <span className={`pill ${item.status}`}>{rel}</span>}
      </div>
      {item.message && <p>{item.message}</p>}
      <details>
        <summary>How this was calculated</summary>
        <ul className="trace">
          {item.explanation.map((step, i) => (
            <li key={i}>
              <code>{step}</code>
            </li>
          ))}
        </ul>
      </details>
      {item.notes.length > 0 && (
        <ul className="notes">
          {item.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
      <div className="muted small source-line">
        <a href={item.source_url} target="_blank" rel="noreferrer">
          Source{item.citation ? ` (${item.citation})` : ""}
        </a>{" "}
        · rule {item.rule_id} v{item.rule_version} · verified {formatDate(item.last_verified)}
        {item.verification === "secondary" && (
          <span className="badge" title="Checked against university pages; confirm with the primary source">
            secondary source
          </span>
        )}
      </div>
    </article>
  );
}

export default function TimelineView({ timeline, schema }: { timeline: Timeline; schema: FactField[] }) {
  const label = new Map(schema.map((f) => [f.name, f.label]));
  const sections: { title: string; items: TimelineItem[] }[] = [
    { title: "Open now and upcoming", items: timeline.items.filter((i) => i.status === "active" || i.status === "upcoming") },
    { title: "Limits and notices", items: timeline.items.filter((i) => i.status === "info") },
    { title: "Already passed", items: timeline.items.filter((i) => i.status === "past") },
  ];

  return (
    <div className="timeline">
      <p className="muted small">As of {formatDate(timeline.as_of)}</p>
      {timeline.items.length === 0 && (
        <p>No dates yet. Fill in a few facts, starting with your program end date.</p>
      )}
      {sections
        .filter((s) => s.items.length)
        .map((s) => (
          <section key={s.title}>
            <h2>{s.title}</h2>
            {s.items.map((item) => (
              <ItemCard key={`${item.rule_id}-${item.label}`} item={item} />
            ))}
          </section>
        ))}
      {timeline.needs_info.length > 0 && (
        <section className="card needs">
          <h2>Add these to see more</h2>
          <ul>
            {timeline.needs_info.map((n) => (
              <li key={n.rule_id}>
                <strong>{n.title}:</strong> {n.missing.map((m) => label.get(m) ?? m).join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}
      {timeline.stale_rules.length > 0 && (
        <div className="banner warn">
          These rules haven&apos;t been re-verified recently: {timeline.stale_rules.join(", ")}.
        </div>
      )}
      <p className="muted small">{timeline.disclaimer}</p>
    </div>
  );
}
