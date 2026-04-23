---
description: Sync all documentation and config after editing pipeline/stages
---

Run this workflow every time you add, remove, or materially change anything inside `pipeline/stages/`.

## 1. Identify what changed

State which stage(s) were touched and what kind of change it was:
- **New detector** (`_1_detect/detectors/<alert_type>/<name>.py`)
- **Modified detector** (threshold, trigger name, signal fields)
- **New gatherer** (`_2_facts/gatherers/<name>.py`)
- **Modified gatherer** (facts produced, signal_type served)
- **New / modified investigator** (`_3_investigate/rule_based.py`, `cortex.py`, or a skill file)
- **New signal type** (new `make_<type>_signal()` factory in `signals.py`)
- **Config change** (`DetectorConfig` fields or YAML defaults)

---

## 2. Stage 1 — Detect changes

If a **detector was added or removed**:
- Update the detector table in `pipeline/docs/architecture.md` (§ Stage 1 — Detect).
- Update the folder tree in `_1_detect/README.md` (§ Architecture code block).
- Update the `_1_detect/README.md` if the new detector uses a new `DetectorConfig` field — add a row to the _Full field reference_ table.

If **signal fields changed** (new / renamed / removed):
- Update the OSA or Compliance signal field table in `_1_detect/README.md` (§ Signal Types).

If **merging rules changed** (`_merge_signals`):
- Update `_1_detect/README.md` (§ Merging).

---

## 3. Stage 2 — Facts changes

If a **gatherer was added or removed**:
- Update the gatherer table in `pipeline/docs/architecture.md` (§ Stage 2 — Facts).
- Update `_2_facts/signal_type_gatherers.yaml` to add/remove the gatherer entry.

If a **gatherer serves a new signal type**:
- Confirm `_2_facts/signal_type_gatherers.yaml` has the correct `signal_types` list.

---

## 4. Stage 3 — Investigate changes

If a **new signal type** is introduced:
- Add a skill file at `_3_investigate/skills/<signal_type_lower>.md`.
- Add an entry to `_3_investigate/signal_type_investigators.yaml` for both `rule_based` and (optionally) `cortex` engines.
- Update `_3_investigate/smart_action_card_content_skill.md` if the card schema changes.

If an **existing rule template** changed in `rule_based.py`:
- Check whether `_3_investigate/skills/` skill files need corresponding updates for Cortex prompts.

---

## 5. Stage 4 — Score changes

If the **scorer logic or sort_value formula** changed:
- Update `pipeline/docs/architecture.md` (§ Stage 4 — Score).

---

## 6. Config changes

If **new thresholds** were added to `DetectorConfig` in `pipeline/pipeline/config.py`:
- Add the field to the _Full field reference_ table in `_1_detect/README.md`.
- Add a default value entry in `config/base/default.yaml` under `thresholds:`.
- Update the `architecture.md` Configuration table if the field affects a new detector.

If a **new detector/gatherer is enabled by default**:
- Add it under `detectors:` or `gatherers:` in `config/base/default.yaml`.

---

## 7. Extensibility table

`pipeline/docs/architecture.md` has an _Extensibility_ table (§ Extensibility). Verify it is still accurate — update it if the contract for adding a new detector, gatherer, or engine has changed.

---

## 8. Folder map

`pipeline/docs/architecture.md` contains a folder map (§ Folder Map). If any files or directories were added or removed inside `stages/`, update that map.

---

## 9. Tests

For every new detector or gatherer:
- Add or update a test in `pipeline/tests/` that exercises the new code path.
- Confirm existing tests still pass:
```
python -m pytest pipeline/tests/ -q
```

---

## 10. Final check

Run a quick grep to catch any stale references to old names (trigger names, field names, file paths):
```
grep -r "<old_name>" pipeline/
```

Confirm:
- [ ] `architecture.md` detector and gatherer tables are current
- [ ] `_1_detect/README.md` signal fields and config table are current
- [ ] `signal_type_gatherers.yaml` and `signal_type_investigators.yaml` are current
- [ ] `config/base/default.yaml` thresholds and enabled lists are current
- [ ] Tests pass
