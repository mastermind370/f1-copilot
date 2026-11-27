// Roommate profile: 8 questions, 3 ordered answers each (0, 1, 2).
// A share code is "RM1-" + one digit per question, e.g. RM1-01210021. No personal data is
// encoded, so codes are safe to post in group chats.

export const QUESTIONS = ["sleep", "clean", "guests", "noise", "food", "cook", "smoke", "budget"] as const;
export type Question = (typeof QUESTIONS)[number];
export type Answers = Partial<Record<Question, 0 | 1 | 2>>;

// Some differences matter more than others when you share a home.
const WEIGHTS: Record<Question, number> = {
  sleep: 2, clean: 2, guests: 1, noise: 2, food: 1, cook: 1, smoke: 3, budget: 3,
};

export function isComplete(a: Answers): a is Record<Question, 0 | 1 | 2> {
  return QUESTIONS.every((q) => a[q] !== undefined);
}

export function encode(a: Record<Question, 0 | 1 | 2>): string {
  return `RM1-${QUESTIONS.map((q) => a[q]).join("")}`;
}

export function decode(code: string): Record<Question, 0 | 1 | 2> | null {
  const m = /^RM1-([0-2]{8})$/.exec(code.trim().toUpperCase());
  if (!m) return null;
  const out = {} as Record<Question, 0 | 1 | 2>;
  QUESTIONS.forEach((q, i) => {
    out[q] = Number(m[1][i]) as 0 | 1 | 2;
  });
  return out;
}

/** Weighted similarity in [0, 100]. Each answer gap of 0/1/2 costs 0/0.5/1 of that weight. */
export function compatibility(a: Record<Question, 0 | 1 | 2>, b: Record<Question, 0 | 1 | 2>) {
  let total = 0;
  let lost = 0;
  const differences: Question[] = [];
  for (const q of QUESTIONS) {
    const gap = Math.abs(a[q] - b[q]);
    total += WEIGHTS[q];
    lost += (WEIGHTS[q] * gap) / 2;
    if (gap > 0) differences.push(q);
  }
  differences.sort((x, y) => WEIGHTS[y] * Math.abs(a[y] - b[y]) - WEIGHTS[x] * Math.abs(a[x] - b[x]));
  return { percent: Math.round(100 * (1 - lost / total)), differences };
}
