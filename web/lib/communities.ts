// Curated group chats. Links are accepted only on known platforms, so a typo or a phishing
// look-alike domain fails `npm test` (and therefore CI) before it can reach students.

export const PLATFORMS = {
  groupme: { label: "GroupMe", color: "#00aff0", hosts: ["groupme.com", "web.groupme.com"], paths: [/^\/join_group\//] },
  whatsapp: { label: "WhatsApp", color: "#25d366", hosts: ["chat.whatsapp.com"], paths: [/^\/[A-Za-z0-9]+$/] },
  discord: { label: "Discord", color: "#5865f2", hosts: ["discord.gg", "discord.com"], paths: [/^\/[A-Za-z0-9-]+$/, /^\/invite\/[A-Za-z0-9-]+$/] },
  telegram: { label: "Telegram", color: "#229ed9", hosts: ["t.me"], paths: [/^\/[A-Za-z0-9_+]+$/] },
  slack: { label: "Slack", color: "#4a154b", hosts: ["join.slack.com"], paths: [/^\/t\//] },
  wechat: { label: "WeChat", color: "#07c160", hosts: [], paths: [] },
} as const;

export type Platform = keyof typeof PLATFORMS;

export interface Community {
  platform: Platform;
  name: string;
  owner: string; // the organization or officer responsible
  url?: string; // invite link (all platforms except WeChat)
  qr?: string; // WeChat only: /communities/qr/<file>.png
  verified: string; // YYYY-MM-DD, last checked by a maintainer
  languages?: string[];
}

export interface CommunityFile {
  version: number;
  schools: Record<string, Community[]>;
}

export const WECHAT_QR_DAYS = 7;

export function validateCommunity(c: Community, where: string): string[] {
  const errs: string[] = [];
  const p = PLATFORMS[c.platform as Platform];
  if (!p) return [`${where}: unknown platform "${c.platform}"`];
  if (!c.name?.trim()) errs.push(`${where}: name is required`);
  if (!c.owner?.trim()) errs.push(`${where}: owner is required (who runs this group?)`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(c.verified ?? "") || Number.isNaN(Date.parse(c.verified))) {
    errs.push(`${where}: verified must be a YYYY-MM-DD date`);
  }
  if (c.platform === "wechat") {
    if (c.url) errs.push(`${where}: WeChat groups have no web links; use a QR image instead`);
    if (!c.qr || !/^\/communities\/qr\/[a-z0-9-]+\.(png|jpg|webp)$/.test(c.qr)) {
      errs.push(`${where}: WeChat needs qr: /communities/qr/<name>.png`);
    }
    return errs;
  }
  if (c.qr) errs.push(`${where}: only WeChat entries use QR images`);
  let u: URL;
  try {
    u = new URL(c.url ?? "");
  } catch {
    return [...errs, `${where}: url is not a valid link`];
  }
  if (u.protocol !== "https:") errs.push(`${where}: url must use https`);
  if (!(p.hosts as readonly string[]).includes(u.hostname)) {
    errs.push(`${where}: ${u.hostname} is not an allowed ${p.label} domain`);
  } else if (!p.paths.some((re) => re.test(u.pathname))) {
    errs.push(`${where}: ${u.pathname} doesn't look like a ${p.label} invite`);
  }
  if (u.username || u.password || u.port) errs.push(`${where}: url must not contain credentials or ports`);
  return errs;
}

export function validateFile(file: CommunityFile, knownSchools: string[]): string[] {
  const errs: string[] = [];
  for (const [school, list] of Object.entries(file.schools ?? {})) {
    if (!knownSchools.includes(school)) errs.push(`unknown school id "${school}"`);
    list.forEach((c, i) => errs.push(...validateCommunity(c, `${school}[${i}]`)));
  }
  return errs;
}

export function daysSince(iso: string, today: string): number {
  return Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${iso}T00:00:00Z`)) / 86_400_000);
}
