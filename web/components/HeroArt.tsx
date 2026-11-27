// Original decorative illustration for the home hero: a study document, a calendar with a
// highlighted deadline, and a flight path around a globe. Pure SVG, no external images.

export default function HeroArt() {
  return (
    <svg viewBox="0 0 520 340" className="hero-art" role="img" aria-label="">
      <defs>
        <linearGradient id="ha-sky" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: "var(--primary-soft)" }} />
          <stop offset="1" style={{ stopColor: "var(--amber-soft)" }} />
        </linearGradient>
        <linearGradient id="ha-globe" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: "var(--primary)" }} />
          <stop offset="1" style={{ stopColor: "var(--primary-deep)" }} />
        </linearGradient>
        <filter id="ha-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#1C2340" floodOpacity="0.14" />
        </filter>
      </defs>

      <rect x="0" y="0" width="520" height="340" rx="28" fill="url(#ha-sky)" />
      <circle cx="430" cy="70" r="90" fill="#FFFFFF" opacity="0.45" />
      <circle cx="70" cy="300" r="110" fill="#FFFFFF" opacity="0.35" />

      {/* globe */}
      <g transform="translate(372 196)">
        <circle r="78" fill="url(#ha-globe)" />
        <ellipse rx="78" ry="28" fill="none" stroke="#FFFFFF" strokeOpacity="0.35" strokeWidth="2" />
        <ellipse rx="30" ry="78" fill="none" stroke="#FFFFFF" strokeOpacity="0.35" strokeWidth="2" />
        <path d="M-78 0h156M0 -78v156" stroke="#FFFFFF" strokeOpacity="0.25" strokeWidth="2" />
        <path d="M-40 -30c14-10 30-6 38 4s24 8 30-2M-52 24c18 6 30 18 52 10s30 2 38 10"
          fill="none" stroke="#FFFFFF" strokeWidth="5" strokeLinecap="round" opacity="0.7" />
      </g>

      {/* flight path */}
      <path d="M118 92 C 210 20, 330 30, 410 110" fill="none" style={{ stroke: "var(--primary)" }} strokeWidth="2.5"
        strokeDasharray="2 9" strokeLinecap="round" opacity="0.55" />
      <g transform="translate(410 110) rotate(42)">
        <path d="M0 -10 L6 8 L0 4 L-6 8 Z" style={{ fill: "var(--accent)" }} />
      </g>

      {/* document card */}
      <g transform="translate(70 120) rotate(-6)" filter="url(#ha-shadow)">
        <rect width="190" height="150" rx="16" fill="#FFFFFF" />
        <rect x="18" y="18" width="70" height="10" rx="5" style={{ fill: "var(--primary)" }} />
        <rect x="18" y="40" width="154" height="7" rx="3.5" fill="#E4E7F2" />
        <rect x="18" y="56" width="128" height="7" rx="3.5" fill="#E4E7F2" />
        <rect x="18" y="72" width="140" height="7" rx="3.5" fill="#E4E7F2" />
        <rect x="18" y="104" width="80" height="26" rx="8" style={{ fill: "var(--primary-soft)" }} />
        <path d="M30 118c8-10 16 6 24-4s12 4 20-2" fill="none" style={{ stroke: "var(--primary)" }} strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="150" cy="116" r="20" fill="none" style={{ stroke: "var(--accent)" }} strokeWidth="3" />
        <path d="M141 116l6 6 11-12" fill="none" style={{ stroke: "var(--accent)" }} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* calendar card */}
      <g transform="translate(232 54) rotate(5)" filter="url(#ha-shadow)">
        <rect width="132" height="124" rx="16" fill="#FFFFFF" />
        <rect width="132" height="32" rx="16" style={{ fill: "var(--primary)" }} />
        <rect y="16" width="132" height="16" style={{ fill: "var(--primary)" }} />
        <circle cx="34" cy="16" r="4" fill="#FFFFFF" />
        <circle cx="98" cy="16" r="4" fill="#FFFFFF" />
        {[0, 1, 2, 3].map((row) =>
          [0, 1, 2, 3, 4].map((col) => {
            const hot = row === 2 && col === 3;
            return (
              <rect key={`${row}-${col}`} x={14 + col * 22} y={44 + row * 19} width="16" height="12" rx="4"
                style={{ fill: hot ? "var(--accent)" : "#EEF0F6" }} />
            );
          }),
        )}
      </g>
    </svg>
  );
}
