"""
Narrative Generator: Snowflake Cortex LLM
==========================================
Produces the four alert card narrative fields by calling Snowflake Cortex
(mistral-large2).  The content rules are composed from two skill files:

1. ``smart_action_card_content_skill.md`` — overall card anatomy and tone rules
2. ``skills/<signal_type>_investigation_skill.md`` — per-alert-type investigation
   steps, loaded from the path declared in ``signal_type_investigators.yaml``.

Falls back to the rule-based generator automatically if:
- The Cortex call raises an exception
- The response is not valid JSON
- Any of the four required keys are missing from the response

Usage
-----
To switch the pipeline to use Cortex narratives, change one line in
``investigate.py``:

    from store_insight.pipeline.stages._4_investigate.cortex import generate

The function signature is identical to ``rule_based.generate`` but requires
the Snowpark session to be passed as a second argument.  ``investigate.py``
handles the dispatch.

Public API
----------
    generate(signal: dict, session) -> dict
    Returns {issue, explanation, cost_if_not_fixed, recommended_action}
"""

import json
import re
import threading
import time
from pathlib import Path

from store_insight.pipeline.stages._4_investigate.cortex_budget import (
    CortexBudget,
    estimate_tokens,
)
from store_insight.pipeline.stages._4_investigate.quality import validate_quality
from store_insight.pipeline.stages._4_investigate.rule_based import generate as rule_based_generate

_HERE = Path(__file__).parent
_CARD_SKILL_PATH = _HERE / "smart_action_card_content_skill.md"
_card_skill_cache: str | None = None
_type_skill_cache: dict = {}
_CORTEX_CALL_LOCK = threading.Lock()  # serialise Snowpark session access


def _load_card_skill() -> str:
    """Load the overall card anatomy + tone skill (cached)."""
    global _card_skill_cache
    if _card_skill_cache is None:
        _card_skill_cache = _CARD_SKILL_PATH.read_text(encoding="utf-8")
    return _card_skill_cache


def _load_type_skill(signal_type: str) -> str:
    """Load the per-signal-type investigation skill (cached), or empty string if absent."""
    if signal_type not in _type_skill_cache:
        # Resolve skill_file path from the YAML mapping at runtime to avoid a
        # circular import (investigate.py imports this module).
        import yaml

        yaml_path = _HERE / "signal_type_investigators.yaml"
        config = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        rel_path = config.get(signal_type, {}).get("skill_file", "")
        if rel_path:
            full_path = _HERE / rel_path
            _type_skill_cache[signal_type] = (
                full_path.read_text(encoding="utf-8") if full_path.exists() else ""
            )
        else:
            _type_skill_cache[signal_type] = ""
    return _type_skill_cache[signal_type]


def _extract_json(text):
    """Strip markdown fences and extract first JSON object from LLM response."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text.strip()


def _build_context(signal):
    """Build a structured text block of signal facts for the LLM prompt.

    Dispatches on ``signal_type``; falls back to the OSA context builder
    for unknown types (which behave like OSA-shaped signals).
    """
    builder = _CONTEXT_BUILDERS.get(signal.get("signal_type"), _build_osa_context)
    return builder(signal)


def _build_compliance_context(signal):
    """Build context block for a TICK_AND_FLICK compliance signal."""
    facts = signal.get("facts", {})
    store_label = signal.get("site_name") or f"Store {signal['store_id']}"
    lines = [
        "Alert Type: Tick-and-Flick Compliance",
        f"Store: {store_label}",
        f"This Week Alerts Worked: {signal.get('this_week_worked', 0)}",
        f"This Week Tick-and-Flick Count: {signal.get('this_week_tf', 0)}",
        f"This Week Tick-and-Flick Rate: {signal.get('this_week_tf_rate', 0.0):.1f}%",
        f"Last Week Tick-and-Flick Rate: {signal.get('last_week_tf_rate', 0.0):.1f}%",
        f"Week-on-Week Rate Change: {signal.get('tf_rate_change', 0.0):+.1f}pp",
        f"Chain Average Tick-and-Flick Rate: {signal.get('chain_tf_rate', 0.0):.1f}%",
        f"Above Chain Average By: {signal.get('above_chain_by', 0.0):+.1f}pp",
    ]
    tf_by_type = facts.get("tf_by_alert_type", [])
    if tf_by_type:
        lines.append("Worst Alert Types by Tick-and-Flick Rate:")
        for item in tf_by_type[:3]:
            lines.append(
                f"  {item['alert_type']}: {item['tf_count']} of {item['worked']} ({item['tf_rate']:.1f}%)"
            )
    return "\n".join(lines)


def _fmt_lsv_composition_line(composition: dict) -> str:
    """Format the upstream / store-process split for the OSA context."""
    buckets = composition.get("buckets", {})
    parts = []
    for key, label in (("store_process", "store process"), ("upstream", "upstream")):
        bucket = buckets.get(key)
        if bucket and bucket.get("lsv", 0) > 0:
            parts.append(f"{label} {bucket['pct']:.1f}% (\u00a3{bucket['lsv']:.2f})")
    if not parts:
        return ""
    return "Lost Sales Composition: " + ", ".join(parts)


def _build_osa_context(signal):
    """Build context block for an OSA availability signal."""
    facts = signal["facts"]
    lines = [
        f"Department: {signal['department']}",
        f"This Week Lost Sales: \u00a3{signal['this_week_lsv']:.2f}",
    ]
    if facts.get("lsv_composition"):
        comp_line = _fmt_lsv_composition_line(facts["lsv_composition"])
        if comp_line:
            lines.append(comp_line)
    if signal.get("this_week_osa"):
        lines.append(f"Store OSA: {signal['this_week_osa']:.1f}%")
    if signal.get("last_week_osa"):
        lines.append(f"Last Week OSA: {signal['last_week_osa']:.1f}%")
    if facts.get("chain_this_week_osa"):
        gap = facts["chain_this_week_osa"] - (signal.get("this_week_osa") or 0)
        lines.append(f"Chain Average OSA: {facts['chain_this_week_osa']:.1f}%")
        lines.append(f"Gap vs Chain: {gap:.1f}pp")
    if "WOW" in signal["trigger_types"] and signal.get("wow_drift_pp"):
        lines.append(f"Week-on-Week OSA Change: {signal['wow_drift_pp']:+.1f}pp")
    if "REPEAT" in signal["trigger_types"] and signal.get("repeat_item_count"):
        lines.append(f"Repeat Alert Items: {signal['repeat_item_count']}")
        repeat_items = signal.get("repeat_item_details", [])
        if repeat_items:
            lines.append("Top Repeat Offender Items:")
            for item in repeat_items[:5]:
                lines.append(
                    f"  {item['ppg']} ({item['subclass']}): triggered {item['alert_weeks']} weeks, "
                    f"\u00a3{item['cumulative_lsv']:,.2f} cumulative lost sales, "
                    f"avg alert-week OSA {item['avg_alert_osa']:.1f}%"
                )
    contributors = facts.get("subclass_contributors", [])
    if contributors:
        lines.append("Top Subclasses by This-Week Lost Sales:")
        for item in contributors[:5]:
            lines.append(
                f"  {item['subclass_name']}: \u00a3{item['this_week_lsv']:,.2f} this week "
                f"(last week \u00a3{item['last_week_lsv']:,.2f}, {item['lsv_change']:+,.2f} change)"
            )
    changes = facts.get("subclass_changes", [])
    if changes:
        lines.append("Subclasses With Biggest Week-on-Week Lost Sales Increase:")
        for item in changes[:5]:
            lines.append(
                f"  {item['subclass_name']}: {item['lsv_change']:+,.2f} change "
                f"(\u00a3{item['this_week_lsv']:,.2f} this week)"
            )
    if facts.get("worst_day"):
        lines.append(
            f"Worst Day: {facts['worst_day']['day']} (\u00a3{facts['worst_day']['lsv']:.2f})"
        )
    lines.append(f"4-Week Projection: \u00a3{facts['cost_projection']:.2f}")
    return "\n".join(lines)


def _build_markdown_override_context(signal):
    """Build context block for a MARKDOWN_OVERRIDE signal."""
    facts = signal.get("facts", {})
    store_label = signal.get("site_name") or f"Store {signal['store_id']}"
    this_rate = signal.get("this_week_override_rate", 0.0)
    lines = [
        "Alert Type: Markdown Override",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Override Rate: {this_rate:.1f}%",
        f"This Week Markdowns: {signal.get('this_week_total_markdowns', 0)}",
        f"This Week Overrides: {signal.get('this_week_overrides', 0)}",
    ]
    if signal.get("last_week_override_rate") is not None:
        lines.append(f"Last Week Override Rate: {signal['last_week_override_rate']:.1f}%")
    if signal.get("wow_change_pp") is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get("chain_override_rate") is not None:
        lines.append(f"Chain Average Override Rate: {signal['chain_override_rate']:.1f}%")
    if signal.get("above_chain_pp") is not None:
        lines.append(f"Above Chain Average By: {signal['above_chain_pp']:+.1f}pp")
    dept_bdwn = facts.get("override_dept_breakdown", [])
    if dept_bdwn:
        lines.append("Top Departments by Overrides:")
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('overrides', 0)} overrides "
                f"({item.get('override_rate_pct', 0.0):.1f}%)"
            )
    return "\n".join(lines)


def _build_waste_context(signal):
    """Build context block for a WASTE-to-markdown-ratio signal."""
    facts       = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    this_rate   = signal.get('this_week_stb_rate', 0.0)
    lines = [
        "Alert Type: Waste-to-Markdown Ratio",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Waste-to-Markdown Ratio: {this_rate:.1f}%",
        f"This Week Waste Quantity: {signal.get('this_week_waste_qty', 0)}",
        "Limitation: the source data cannot show whether individual wasted units were marked down before disposal.",
        f"This Week Waste Value: \u00a3{signal.get('this_week_waste_value', 0.0):,.2f}",
    ]
    if signal.get('last_week_stb_rate') is not None:
        lines.append(f"Last Week Waste-to-Markdown Ratio: {signal['last_week_stb_rate']:.1f}%")
    if signal.get('wow_change_pp') is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get('chain_stb_rate') is not None:
        lines.append(f"Chain Average Waste-to-Markdown Ratio: {signal['chain_stb_rate']:.1f}%")
    if signal.get('above_chain_pp') is not None:
        lines.append(f"Above Chain Average By: {signal['above_chain_pp']:+.1f}pp")
    dept_bdwn = facts.get("waste_dept_breakdown", [])
    if dept_bdwn:
        lines.append("Top Departments by Waste:")
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('waste_qty', 0)} wasted units, "
                f"\u00a3{item.get('waste_value', 0.0):,.2f} "
                "at original price"
            )
    return "\n".join(lines)


def _build_markdown_sellthrough_context(signal):
    """Build context block for a MARKDOWN_SELLTHROUGH signal."""
    facts = signal.get("facts", {})
    store_label = signal.get("site_name") or f"Store {signal['store_id']}"
    this_rate = signal.get("this_week_sellthrough_rate", 0.0)
    lines = [
        "Alert Type: Markdown Sell-Through",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Sell-Through Rate: {this_rate:.1f}%",
        f"This Week Markdown Quantity: {signal.get('this_week_markdown_qty', 0)}",
        f"This Week Markdown Value: \u00a3{signal.get('this_week_markdown_value', 0.0):,.2f}",
    ]
    if signal.get("last_week_sellthrough_rate") is not None:
        lines.append(f"Last Week Sell-Through Rate: {signal['last_week_sellthrough_rate']:.1f}%")
    if signal.get("wow_change_pp") is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get("chain_sellthrough_rate") is not None:
        lines.append(f"Chain Average Sell-Through Rate: {signal['chain_sellthrough_rate']:.1f}%")
    if signal.get("below_chain_pp") is not None:
        lines.append(f"Below Chain Average By: {signal['below_chain_pp']:.1f}pp")
    dept_bdwn = facts.get("sellthrough_dept_breakdown", [])
    if dept_bdwn:
        lines.append("Worst Departments by Sell-Through:")
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('sellthrough_rate_pct', 0.0):.1f}% "
                f"on {item.get('requested_qty', 0)} units"
            )
    return "\n".join(lines)


def _build_markdown_sku_context(signal):
    """Build context block for a MARKDOWN_SKU (SKU-level markdown) signal."""
    facts = signal.get("facts", {})
    store_label = signal.get("site_name") or f"Store {signal['store_id']}"
    item_desc = signal.get("item_description") or f"Item {signal.get('item_id', '')}"
    req_count = signal.get("markdown_request_count") or 0
    override = signal.get("override_count")
    lbk_weeks = signal.get("lookback_weeks", 4)
    lines = [
        "Alert Type: SKU-Level Markdown",
        f"Store: {store_label}",
        f"Item: {item_desc} (ID {signal.get('item_id', '?')})",
        f"Department: {signal.get('department') or 'unknown'}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"Lookback Window: {lbk_weeks} weeks",
        f"Markdown Requests In Window: {req_count}",
    ]
    if override is not None:
        override_rate = round(override / req_count * 100) if req_count else 0
        lines.append(f"Overrides In Window: {override} ({override_rate}% override rate)")
    if signal.get("avg_markdown_pct") is not None:
        lines.append(f"Avg Markdown Depth: {signal['avg_markdown_pct']:.1f}%")
    history = facts.get("sku_markdown_history", [])
    if history:
        lines.append(f"Weekly History (last {len(history)} weeks):")
        for week in history:
            ov_str = f", {week['override_count']} overridden" if week.get("override_count") else ""
            lines.append(
                f"  w/c {week.get('week_start', '?')}: "
                f"{week.get('request_count', 0)} requests{ov_str}"
            )
    return "\n".join(lines)


# Dispatch map used by _build_context. Declared after builders so all names
# resolve. Signal types not listed here fall through to _build_osa_context.
_CONTEXT_BUILDERS = {
    "COMPLIANCE": _build_compliance_context,
    "OSA": _build_osa_context,
    "MARKDOWN_OVERRIDE": _build_markdown_override_context,
    "WASTE": _build_waste_context,
    "MARKDOWN_SELLTHROUGH": _build_markdown_sellthrough_context,
    "MARKDOWN_SKU": _build_markdown_sku_context,
}


def generate(
    signal: dict,
    session,
    budget: CortexBudget | None = None,
    max_retries: int = 2,
    quality_max_action_length: int = 800,
    quality_reject_generic: bool = True,
) -> dict:
    """
    Generate narrative fields using Snowflake Cortex (mistral-large2).

    Parameters
    ----------
    signal                    : dict — output of enrich_signals (Stage 2), contains 'facts' key
    session                   : Snowpark Session
    budget                    : optional CortexBudget — aborts and falls back if exceeded
    max_retries               : number of retries on transient failures (default 2)
    quality_max_action_length : max length of recommended_action (default 800)
    quality_reject_generic    : flag generic/vague recommendations (default True)

    Returns
    -------
    dict with keys: issue, explanation, cost_if_not_fixed, recommended_action
    Falls back to rule_based.generate on budget, quality, or call failures.
    """
    card_skill = _load_card_skill()
    type_skill = _load_type_skill(signal.get("signal_type", ""))
    context = _build_context(signal)

    skill_block = card_skill
    if type_skill:
        skill_block += (
            f"\n\n--- INVESTIGATION SKILL ---\n{type_skill}\n--- END INVESTIGATION SKILL ---"
        )

    prompt = (
        "You are a retail analyst writing content for a Smart Action Card for a store manager.\n"
        "Follow the Content Skill rules below exactly.\n\n"
        "--- CONTENT SKILL ---\n"
        f"{skill_block}\n"
        "--- END CONTENT SKILL ---\n\n"
        "--- SIGNAL DATA ---\n"
        f"{context}\n"
        "--- END SIGNAL DATA ---\n\n"
        "Using the Content Skill rules and the signal data above, return ONLY a JSON object "
        "with these four keys:\n"
        '  "issue"               \u2014 title slot\n'
        '  "explanation"         \u2014 summary sentence + worst day callout\n'
        '  "cost_if_not_fixed"   \u2014 cost panel sentence\n'
        '  "recommended_action"  \u2014 action panel (2\u20134 sentences)\n\n'
        "Do not restate the full subclass contributor or repeat-offender item lists as a "
        "bulleted list \u2014 those are rendered separately from structured data. However, you "
        "should use them to make the recommended_action specific: name the 1\u20132 worst "
        "subclasses or repeat-offender items by name (e.g. 'starting with BEERS & LAGERS' or "
        "'especially the 4238 CITRUS line') so the manager knows exactly where to look first. "
        "Never fabricate a name that is not present in the signal data above.\n"
        "Output raw JSON only. Do not wrap in markdown fences."
    )

    prompt_escaped = prompt.replace("'", "''")
    estimated_tokens = estimate_tokens(prompt)

    # Budget gate: abort before spending a call if budget is exhausted.
    if budget is not None and not budget.record(estimated_tokens):
        _label = signal.get("department") or signal.get("signal_type", "?")
        print(
            f"[3_investigate/cortex] Budget exceeded for store {signal['store_id']} "
            f"{_label} — falling back to rule-based."
        )
        fallback = rule_based_generate(signal)
        fallback["_prompt"] = prompt
        fallback["_raw_response"] = ""
        fallback["_fallback_reason"] = "budget_exceeded"
        return fallback

    # Call Cortex with exponential-backoff retries.
    raw_response = ""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            with _CORTEX_CALL_LOCK:
                result = session.sql(
                    f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', '{prompt_escaped}') AS RESPONSE"
                ).collect()
            raw_response = result[0]["RESPONSE"].strip()
            break
        except Exception as e:
            last_error = e
            _label = signal.get("department") or signal.get("signal_type", "?")
            print(
                f"[3_investigate/cortex] Cortex call attempt {attempt + 1} failed for store "
                f"{signal['store_id']} {_label}: {e}"
            )
            if attempt < max_retries:
                time.sleep(2**attempt)
            else:
                print(
                    f"[3_investigate/cortex] All retries exhausted for store {signal['store_id']} "
                    f"{_label} — falling back to rule-based."
                )
                fallback = rule_based_generate(signal)
                fallback["_prompt"] = prompt
                fallback["_raw_response"] = raw_response
                fallback["_fallback_reason"] = f"cortex_error: {last_error}"
                return fallback

    # Parse and validate the response.
    try:
        cleaned = _extract_json(raw_response)
        narrative = json.loads(cleaned)
    except json.JSONDecodeError as e:
        _label = signal.get("department") or signal.get("signal_type", "?")
        print(
            f"[3_investigate/cortex] Invalid JSON for store {signal['store_id']} "
            f"{_label}: {e} — falling back to rule-based."
        )
        fallback = rule_based_generate(signal)
        fallback["_prompt"] = prompt
        fallback["_raw_response"] = raw_response
        fallback["_fallback_reason"] = f"invalid_json: {e}"
        return fallback

    # JSON-level required keys check (kept alongside quality check for clarity).
    required = ["issue", "explanation", "cost_if_not_fixed", "recommended_action"]
    if not all(k in narrative for k in required):
        _label = signal.get("department") or signal.get("signal_type", "?")
        print(
            f"[3_investigate/cortex] Missing fields for store {signal['store_id']} "
            f"{_label} — falling back to rule-based. "
            f"Keys received: {list(narrative.keys())}"
        )
        fallback = rule_based_generate(signal)
        fallback["_prompt"] = prompt
        fallback["_raw_response"] = raw_response
        fallback["_fallback_reason"] = "missing_fields"
        return fallback

    # Quality gate: generic/None/nan/too-long checks.
    is_valid, reason = validate_quality(
        narrative,
        max_action_length=quality_max_action_length,
        reject_generic=quality_reject_generic,
    )
    if is_valid:
        narrative["_prompt"] = prompt
        narrative["_raw_response"] = raw_response
        narrative["_fallback_reason"] = ""
        return narrative

    _label = signal.get("department") or signal.get("signal_type", "?")
    print(
        f"[3_investigate/cortex] Quality check failed for store {signal['store_id']} "
        f"{_label}: {reason} — falling back to rule-based."
    )
    fallback = rule_based_generate(signal)
    fallback["_prompt"] = prompt
    fallback["_raw_response"] = raw_response
    fallback["_fallback_reason"] = f"quality_check: {reason}"
    return fallback
