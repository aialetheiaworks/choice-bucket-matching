# Feedback from CHOICE testing — Tooltip (Bucket Matching Engine) · 1 Oct 2026

CHOICE (the product in `../CHOICE`) calls this engine's `POST /tooltip` with the owner's draft objective and
shows the ranked prompts on its **Reflect** screen ("Also consider…"). This file is feedback from a full
walkthrough with a real-sounding case. It is self-contained: you don't need the CHOICE conversation.

## The case

Draft statement sent to `/tooltip`:

> The owners of the tuition centre in Indore with 120 students in classes 9 to 12 want to establish online
> classes before the next academic year starts in April, while keeping fees the same, and are deciding between
> building their own online learning app or using an existing platform like Zoom.

Prompts returned (9, in this order):
1. Consider strategic fit and long-term roadmap.
2. Consider technical feasibility, architecture, and constraints.
3. Identify the customer's underlying jobs, pain points, motivations, expected outcomes, and unmet needs.
4. Consider target business outcomes, KPIs, and success criteria.
5. Consider implementation, operational, and lifecycle costs.
6. Consider objective decision criteria and trade-offs.
7. Consider prioritization, technical debt, and backlog health.
8. Consider rollout approach, phases, and execution.
9. Consider architecture, scalability, performance, integration, technical risks, and implementation complexity.

## What's wrong (from the owner's point of view)

1. **Too many.** Nine prompts on one screen for a small-business owner. The design brief's intent was a short
   list (TOP_N = 5); ties raise it to MAX_N = 9 (raised from 7 on 2026-09-01 for recall, per `get_tooltip.py`).
2. **Too technical for this owner.** Four of nine are software-engineering prompts (#2, #7, #9, and partly #8):
   "technical debt, and backlog health", "architecture, scalability, performance…". A tuition-centre owner
   choosing between "build an app" and "use Zoom" needs "who will run it", "what it costs over time", "what
   parents need", not backlog health. The words "app" and "platform" seem to pull in the IT buckets.
3. **Near-duplicates.** #2 (technical feasibility, architecture, constraints) and #9 (architecture, scalability,
   performance, integration, technical risks, complexity) say nearly the same thing; the existing
   near-duplicate collapse (`rank_buckets`, "bucket-overlap" dedupe) didn't catch them.
4. **Missing angle.** Nothing on competition, though the question says two students left for an online app
   (Market / Competitive landscape bucket would fit).

## Suggested direction (your call)

- **Show at most 5–6 in CHOICE**, even when ties would allow 9. Options: keep MAX_N=9 for recall in the eval,
  but add a display cap parameter to `/tooltip` (e.g. `max_lines`, default unchanged), so CHOICE can ask for 6
  without changing your eval numbers.
- **Diversify across bucket families** before cutting: at most one or two engineering/technology buckets in
  the shown list, so business angles (customer, cost, market, people, risk) aren't crowded out.
- **Treat #2 and #9 as duplicates** (content overlap on "architecture/technical"), keep the tier-1 one.
- Consider down-weighting deep IT buckets (technical debt, backlog, scalability) when the statement reads like
  a small business ("our students", "our staff", "tuition centre", "café") rather than a software team.

## How to check

- Re-run your eval harness (`eval_harness.py`, `eval_set.json`) and keep recall at least where it is.
- Run the statement above: expect ≤6 prompts, ≤2 technical, and #2/#9 not both shown.
- Also try: "We run a 20-seat café in Koregaon Park, Pune… either starting delivery through Swiggy and Zomato,
  or partnering with a nearby office park…" (CHOICE's other test case).

## Don't break (CHOICE depends on these)

- `POST /tooltip` with `{"master_prompt": "..."}` and the response shape: `ranked[]` items with `id`, `name`,
  `tier`, `prompt`, `score`, `matched_terms`, `tooltip_line`. Adding an optional request field is fine.
- CHOICE runs this service locally on port 8102 (`../CHOICE/scripts/services.sh restart reflect`).
