# Planted patterns

Each pattern exists only as raw signals (events, survey scores, overtime, free text). Nothing labels it. The pipeline, Genie Agents and the attrition model each have to find it. Dates are offsets from the stored seed end date (T); increments do not move them. Sizes are for 5,000 employees and scale with `--num-employees`.

## P1. Contact-center attrition spike

- **Where:** Consumer Banking, Charlotte and Phoenix contact centers (~200 each). Columbus is the control.
- **When:** `site_events` records a schedule change at both centers at T-8 months. At the same time, three newly assigned team managers take over teams there. `manager_change` events go to every member active on that date, including people who leave later.
- **Signals after the change:** overtime +40% at the two centers; `q_workload` and engagement drop; survey comments mention shifts and schedules; voluntary exits run about 2.5x the prior-year rate, with about 60% of the excess under the three managers; about 70% of their exit interviews give schedule and workload as the main reason.
- **Expected:** YTD voluntary attrition at the two centers is roughly double the prior two years; top AI-classified reason is schedule and workload; the highest model risk scores cluster there, with manager change and overtime trend as top drivers.

## P2. Under-recognized high performers in AI and data roles

- **Where:** ~30 people, mostly Technology AI and data roles, a few analytics roles in other lines.
- **Signals:** rating 4 or 5 in both review cycles; `last_promotion_date` more than 3 years before T; base salary below 92% of band midpoint; manager comments praise specific skills; engagement `q_growth` low.
- **Expected:** they top the "high performers not promoted or paid below midpoint" list and carry elevated flight risk.

## P3. License and training gap in Wealth Northeast

- **Where:** Wealth Management, Northeast region (~180 advisors).
- **Signals:** ~25 licensed staff with `expiry_date` within 60 days of T (about 5x the rate elsewhere in Wealth); `licenses` has a dated `Expiring` status for every licence in that window, not only the planted cohort; ~40% overdue mandatory training versus ~8% baseline; the same group has lower engagement and higher overtime.
- **Expected:** expiring licenses and overdue training concentrate in Wealth Northeast; about 10-15 people are both expiring and high flight risk (the cross-domain demo question).

## P4. Burnout pocket in fraud operations

- **Where:** Operations, fraud operations card disputes teams in the Southeast (~50 of ~150 fraud ops staff).
- **Signals:** overtime +60% for the last 6 months; engagement down across the last three waves; survey comments use burnout language (exhausted, no breaks, unsustainable), giving a burnout flag rate of ~45% versus ~10% baseline.
- **Expected:** a clear burnout pocket. Attrition there is only starting to rise, so it reads as a leading indicator, and model risk scores are trending up.

## P5. Standout managers

- **Where:** ~8 people managers across business lines.
- **Signals:** team voluntary attrition about half the baseline; engagement +0.5 on the index; more promotions from their teams; positive manager-related survey comments.
- **Expected:** they top the best-retention and engagement lists, a contrast to the three P1 managers.

## P6. GenAI-exposed operations roles and adjacent-skill open roles

- **Where:** Operations payments, deposit and loan processing roles (~400 people); ~25 open requisitions for automation, process improvement and fraud data analyst roles.
- **Signals:** job descriptions for the exposed roles are dominated by routine processing tasks; open-role descriptions are consultative and list skills (SQL, process mapping, data quality, Excel automation) that also appear in manager comments for ~60 operations workers.
- **Expected:** `ai_classify` puts the processing roles in the high GenAI exposure tier; skills matching surfaces ~60 internal reskilling candidates for the open roles.
- **Handoff:** the planted P6 requisitions stay open through the Phase 16 window. Ordinary backfill requisitions also appear as Open, so the recruiting pipeline is not only the P6 cohort.

## P7. Licensed-role hiring is slow (for the Recruiting agent)

The doc lists six patterns. This one gives the fourth agent a story.

- **Signals:** licensed-role requisitions take ~60 days to fill versus ~38 for others; Wealth advisor requisitions have few candidates past screening.
- **Expected:** licensed roles take noticeably longer to fill; the pipeline is thinnest for Wealth advisors.

## Target questions

Each question has a planted answer. Exact expected values are computed from the generated data and stored with each agent's benchmarks in `src/genie/`.

| # | Agent | Question | Pattern |
|---|---|---|---|
| 1 | Workforce & Attrition | How has voluntary attrition tracked YTD versus the last two years? | P1 |
| 2 | Workforce & Attrition | What's driving contact-center attrition? | P1 |
| 3 | Workforce & Attrition | Who are my highest flight risks and why? | P1, P3 (model) |
| 4 | Workforce & Attrition | Any burnout pockets? | P4 |
| 5 | Workforce & Attrition | Which managers have the best retention and engagement? | P5 |
| 6 | Talent & Performance | Senior high performers not promoted in 3+ years or paid below midpoint? | P2 |
| 7 | Talent & Performance | Which roles are most exposed to GenAI? | P6 |
| 8 | Talent & Performance | Who could be reskilled into our open roles? | P6 |
| 9 | Regulated Workforce | Licensed staff with licenses expiring in 60 days? | P3 |
| 10 | Regulated Workforce | Overdue mandatory training by branch or office? | P3 |
| 11 | Recruiting | Time to fill for licensed roles versus others? | P7 |
| 12 | Recruiting | Where is the pipeline thin? | P7 |
| 13 | Cross-domain | Which licensed staff have licenses expiring in 60 days and are also high flight risks? | P3 + model |
| 14 | Follow-up to 13 | Break that down by branch. | P3 |

## Pattern checks

`tests/test_patterns.py` checks each pattern on the raw files at 500 employees, for example:

- **P1:** after the change, the spike centers' monthly voluntary exit rate is at least 2x Columbus, and schedule and workload is the most common ground-truth exit reason there.
- **P3:** Wealth Northeast's share of licenses expiring within 60 days is at least 3x the rest of Wealth.
- **P4:** the card disputes teams' average overtime over the last 6 months is at least 1.5x other fraud ops teams.

Model-dependent expectations (questions 3 and 13) are checked after Phase 9.
