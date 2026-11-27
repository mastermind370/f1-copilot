import { PLATFORMS, type Platform } from "@/lib/communities";

// Simple colored badges with the platform's initial. No trademarked logos are copied.
const INITIAL: Record<Platform, string> = { groupme: "G", whatsapp: "W", discord: "D", telegram: "T", slack: "S", wechat: "微" };

export default function PlatformIcon({ platform }: { platform: Platform }) {
  const p = PLATFORMS[platform];
  return (
    <span className="platform-icon" style={{ background: p.color }} aria-hidden="true">
      {INITIAL[platform]}
    </span>
  );
}
