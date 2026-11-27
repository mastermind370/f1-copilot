# Email to Rutgers Global (rule review request)

Send it from your Rutgers email and attach `docs/rule-review.md` (or a PDF of it). Find the right
contact on https://global.rutgers.edu/ (the general inbox or an advisor you've met).

---

**Subject:** Student project: would an advisor review 10 F-1 deadline rules? (about 20 minutes)

Hello,

I'm a Computer Engineering sophomore at Rutgers, and I've built a free, open-source tool to help
international students understand F-1 rules. It answers questions using only official sources and
shows where each sentence comes from. It also calculates personal deadlines, like the OPT filing
window and the 60-day grace period, using fixed rules instead of AI.

Every page tells students it isn't legal advice and that they should confirm with their DSO. Before
I share it with other students, I'd like an advisor to check that the rules are correct as general
guidance.

I've attached a short checklist with the 10 rules, what each one calculates, and its source. For
each rule there are three boxes: correct, needs a change, or different at Rutgers. It should take
about 20 minutes. I'm also happy to walk through it in person or on a call.

With your permission, I'd list "reviewed by Rutgers Global on [date]" next to each rule you
approve. If you'd rather not be named, I'll just note that a DSO reviewed it.

The code is public here: https://github.com/mastermind370/f1-copilot

Thank you for your time,

[Your name]
[NetID] · Computer Engineering, Class of [year]

---

After a review: set `verification: primary` only for rules backed by a primary source, add a
`reviewed_by` note and the date to each rule's `changelog`, bump `version` for any rule that
changed, and re-run `copilot rules check`.
