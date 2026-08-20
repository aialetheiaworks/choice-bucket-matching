---
title: CHOICE Bucket Matching Test UI
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# CHOICE Bucket Matching — Test UI

Internal test UI for the CHOICE root-word bucket matching pipeline (see
`CLAUDE_CODE_BUILD_BRIEF.md` and `CHOICE_Bucket_Matching_Requirements.md`
in this repo for the full design). Paste a Choice Forge master prompt and
get back the ranked tooltip lines the matching engine would surface.

Not the production integration — this exists purely so testers can try
the pipeline without using the CLI. See `PHASE6_EVAL_RESULTS.md` for the
current evaluation results (73.3% recall on an 18-case eval set as of
2026-08-20).
