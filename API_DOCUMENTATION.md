# CHOICE Bucket Matching API

A REST API that takes a free-text business statement and returns relevant
"consider also" tooltip prompts, matched against an 80-bucket business
taxonomy (Business Objective, Customer, Risk, Market, Governance, etc.).

**Base URL:** `https://choice-bucket-matching.onrender.com`

**Interactive docs:** `https://choice-bucket-matching.onrender.com/docs`
(Swagger UI — lets you try requests directly in the browser without any
code.)

---

## Endpoints

### `POST /tooltip`

Matches a master prompt against the bucket library and returns ranked
tooltip suggestions.

**Request body:**
```json
{
  "master_prompt": "We want to reduce customer churn by improving our onboarding process."
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `master_prompt` | string | yes | The business statement to match. Must be non-empty after trimming whitespace. |

**Success response — `200 OK`:**
```json
{
  "tooltip_lines": [
    "Consider target business outcomes, KPIs, and success criteria.",
    "Consider customer segment, persona, needs, pain points, and expected outcomes."
  ],
  "ranked": [
    {
      "id": "business_objective",
      "name": "Business Objective",
      "tier": 1,
      "prompt": "Consider target business outcomes, KPIs, and success criteria.",
      "score": 2,
      "matched_terms": ["improve", "reduce"],
      "tooltip_line": "Consider target business outcomes, KPIs, and success criteria."
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `tooltip_lines` | string[] | Pre-rendered display strings, ready to show as-is. |
| `ranked` | object[] | Same data, broken into fields — use this if you want to render tooltips with custom styling instead of the pre-built string. |
| `ranked[].id` | string | Stable bucket identifier. |
| `ranked[].name` | string | Human-readable bucket name. |
| `ranked[].tier` | int | 1 or 2 — which taxonomy tier the bucket belongs to. |
| `ranked[].prompt` | string | The underlying "consider" guidance text for this bucket. |
| `ranked[].score` | int | Number of distinct vocabulary terms matched — higher means a stronger match. Not normalized/percentage, just a raw count. |
| `ranked[].matched_terms` | string[] | Which specific words/phrases in the input triggered this bucket. Useful for debugging why a bucket matched. |
| `ranked[].tooltip_line` | string | Same as the corresponding entry in `tooltip_lines` (and currently identical to `ranked[].prompt` too — kept as a separate field in case the rendering diverges from the raw prompt again later). |

**Result size:** normally up to 5 buckets. Can occasionally return up to 7
if there's a genuine tie at the boundary (all tied buckets are kept rather
than dropped arbitrarily). Can return fewer than 5 if the input doesn't
match that many buckets — this is intentional, not a bug.

**Error responses:**

| Status | When | Body |
|---|---|---|
| `400` | `master_prompt` is empty or whitespace-only | `{"detail": "master_prompt must not be empty"}` |
| `422` | `master_prompt` field missing entirely, or wrong type | `{"detail": [{"type": "missing", "loc": ["body", "master_prompt"], "msg": "Field required", ...}]}` |

---

### `GET /health`

Basic liveness check.

**Response — `200 OK`:**
```json
{ "status": "ok", "buckets_loaded": 80 }
```

---

## Example usage

**cURL:**
```bash
curl -X POST https://choice-bucket-matching.onrender.com/tooltip \
  -H "Content-Type: application/json" \
  -d '{"master_prompt": "We want to reduce customer churn by improving our onboarding process."}'
```

**JavaScript (fetch):**
```javascript
const res = await fetch("https://choice-bucket-matching.onrender.com/tooltip", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ master_prompt: userInputText }),
});
if (!res.ok) {
  const err = await res.json();
  // handle 400 (empty input) or 422 (malformed request)
}
const { tooltip_lines, ranked } = await res.json();
```

---

## Operational notes for integrators

- **Cold starts:** this is hosted on Render's free tier, which spins the
  service down after ~15 minutes of no traffic. The first request after
  an idle period can be slow — potentially several minutes, not the
  typical ~50s Render quotes, because this service loads an NLP model and
  a large vocabulary at startup. Design the frontend to show a loading
  state rather than assuming a fast response on every call, especially
  the first one after a quiet period.
- **No auth currently.** The endpoint is open — do not treat it as
  production-hardened yet. Rate limiting / an API key can be added later
  if this becomes public-facing at scale.
- **CORS:** currently open (`*`). Will be restricted to specific frontend
  origin(s) once that's known — will not require a frontend-side change
  when that happens.
- **Not real-time-sensitive matching:** treat this as a "suggestions"
  feature, not a hard validation gate — a 0-match input isn't an error,
  it falls back to 5 default/core buckets (Business Objective, Customer,
  Value Proposition, Risk, Market).
