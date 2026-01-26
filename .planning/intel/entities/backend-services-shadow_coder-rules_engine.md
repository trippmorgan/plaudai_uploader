---
path: /home/server1/plaudai_uploader/backend/services/shadow_coder/rules_engine.py
type: service
updated: 2026-01-25
status: active
---

# rules_engine.py

## Purpose

Evaluates PAD coding compliance rules against case facts and generates documentation prompts for missing elements. Enforces coding requirements for symptom classification, laterality, hemodynamic documentation, medical management trials, wound documentation, and procedure-specific requirements. Automatically creates, updates, and resolves prompts as facts change, supporting workflow-integrated coding compliance.

## Exports

- `PAD_RULES` - List of rule definitions with conditions, required facts, severity levels, and guideline references
- `RulesEngine` - Main class for rule evaluation
  - `evaluate_pad_rules(case_id): Dict` - Evaluates all rules, returns violations, prompts created/resolved
  - `get_active_prompts(case_id): List` - Retrieves active coding prompts ordered by severity
  - `get_prompt_summary(case_id): Dict` - Returns prompt counts by severity (block/warn/info)

## Dependencies

- [[backend-services-shadow_coder-facts_service]] - FactsService for retrieving case fact values
- sqlalchemy - Database operations for scc_prompt_instances table

## Used By

TBD

## Notes

Rules have three severity levels: block (must resolve before proceeding), warn (should document), info (consider documenting). Rules support conditional evaluation (e.g., ABI only required for claudication, not tissue loss). References clinical guidelines: AUC for PAD Revascularization, TASC II, SVS Guidelines, WIfI Classification, CMS LCD for Carotid Stenting. Prompt actions include: DOCUMENT, SNOOZE_24H, DISMISS.
