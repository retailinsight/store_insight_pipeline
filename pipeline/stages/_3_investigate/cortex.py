"""
Narrative Generator: Snowflake Cortex LLM
==========================================
Produces the four alert card narrative fields by calling Snowflake Cortex
(mistral-large).  The content rules are composed from two skill files:

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

    from store_insight.pipeline.stages._3_investigate.cortex import generate

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
from pathlib import Path

from store_insight.pipeline.stages._3_investigate.rule_based import generate as rule_based_generate


_HERE             = Path(__file__).parent
_CARD_SKILL_PATH  = _HERE / 'smart_action_card_content_skill.md'
_card_skill_cache: str | None = None
_type_skill_cache: dict       = {}


def _load_card_skill() -> str:
    """Load the overall card anatomy + tone skill (cached)."""
    global _card_skill_cache
    if _card_skill_cache is None:
        _card_skill_cache = _CARD_SKILL_PATH.read_text(encoding='utf-8')
    return _card_skill_cache


def _load_type_skill(signal_type: str) -> str:
    """Load the per-signal-type investigation skill (cached), or empty string if absent."""
    if signal_type not in _type_skill_cache:
        # Resolve skill_file path from the YAML mapping at runtime to avoid a
        # circular import (investigate.py imports this module).
        import yaml
        yaml_path = _HERE / 'signal_type_investigators.yaml'
        config    = (yaml.safe_load(yaml_path.read_text(encoding='utf-8')) or {})
        rel_path  = config.get(signal_type, {}).get('skill_file', '')
        if rel_path:
            full_path = _HERE / rel_path
            _type_skill_cache[signal_type] = full_path.read_text(encoding='utf-8') if full_path.exists() else ''
        else:
            _type_skill_cache[signal_type] = ''
    return _type_skill_cache[signal_type]


def _extract_json(text):
    """Strip markdown fences and extract first JSON object from LLM response."""
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.MULTILINE)
    text = re.sub(r'\s*```\s*$', '', text.strip(), flags=re.MULTILINE)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text.strip()


def _build_context(signal):
    """Build a structured text block of signal facts for the LLM prompt.

    Dispatches on ``signal_type``; falls back to the OSA context builder
    for unknown types (which behave like OSA-shaped signals).
    """
    builder = _CONTEXT_BUILDERS.get(signal.get('signal_type'), _build_osa_context)
    return builder(signal)


def _build_compliance_context(signal):
    """Build context block for a TICK_AND_FLICK compliance signal."""
    facts = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    lines = [
        f"Alert Type: Tick-and-Flick Compliance",
        f"Store: {store_label}",
        f"This Week Alerts Worked: {signal.get('this_week_worked', 0)}",
        f"This Week Tick-and-Flick Count: {signal.get('this_week_tf', 0)}",
        f"This Week Tick-and-Flick Rate: {signal.get('this_week_tf_rate', 0.0):.1f}%",
        f"Last Week Tick-and-Flick Rate: {signal.get('last_week_tf_rate', 0.0):.1f}%",
        f"Week-on-Week Rate Change: {signal.get('tf_rate_change', 0.0):+.1f}pp",
        f"Chain Average Tick-and-Flick Rate: {signal.get('chain_tf_rate', 0.0):.1f}%",
        f"Above Chain Average By: {signal.get('above_chain_by', 0.0):+.1f}pp",
    ]
    tf_by_type = facts.get('tf_by_alert_type', [])
    if tf_by_type:
        lines.append('Worst Alert Types by Tick-and-Flick Rate:')
        for item in tf_by_type[:3]:
            lines.append(
                f"  {item['alert_type']}: {item['tf_count']} of {item['worked']} ({item['tf_rate']:.1f}%)"
            )
    return '\n'.join(lines)


def _build_osa_context(signal):
    """Build context block for an OSA availability signal."""
    facts = signal['facts']
    lines = [
        f"Department: {signal['department']}",
        f"This Week Lost Sales: \u00a3{signal['this_week_lsv']:.2f}",
    ]
    if signal.get('this_week_osa'):
        lines.append(f"Store OSA: {signal['this_week_osa']:.1f}%")
    if signal.get('last_week_osa'):
        lines.append(f"Last Week OSA: {signal['last_week_osa']:.1f}%")
    if facts.get('chain_this_week_osa'):
        gap = facts['chain_this_week_osa'] - (signal.get('this_week_osa') or 0)
        lines.append(f"Chain Average OSA: {facts['chain_this_week_osa']:.1f}%")
        lines.append(f"Gap vs Chain: {gap:.1f}pp")
    if 'WOW' in signal['trigger_types'] and signal.get('wow_drift_pp'):
        lines.append(f"Week-on-Week OSA Change: {signal['wow_drift_pp']:+.1f}pp")
    if 'REPEAT' in signal['trigger_types'] and signal.get('repeat_item_count'):
        lines.append(f"Repeat Alert Items: {signal['repeat_item_count']}")
    if facts.get('worst_day'):
        lines.append(
            f"Worst Day: {facts['worst_day']['day']} (\u00a3{facts['worst_day']['lsv']:.2f})"
        )
    lines.append(f"4-Week Projection: \u00a3{facts['cost_projection']:.2f}")
    return '\n'.join(lines)


def _build_markdown_override_context(signal):
    """Build context block for a MARKDOWN_OVERRIDE signal."""
    facts       = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    this_rate   = signal.get('this_week_override_rate', 0.0)
    lines = [
        f"Alert Type: Markdown Override",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Override Rate: {this_rate:.1f}%",
        f"This Week Markdowns: {signal.get('this_week_total_markdowns', 0)}",
        f"This Week Overrides: {signal.get('this_week_overrides', 0)}",
    ]
    if signal.get('last_week_override_rate') is not None:
        lines.append(f"Last Week Override Rate: {signal['last_week_override_rate']:.1f}%")
    if signal.get('wow_change_pp') is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get('chain_override_rate') is not None:
        lines.append(f"Chain Average Override Rate: {signal['chain_override_rate']:.1f}%")
    if signal.get('above_chain_pp') is not None:
        lines.append(f"Above Chain Average By: {signal['above_chain_pp']:+.1f}pp")
    dept_bdwn = facts.get('override_dept_breakdown', [])
    if dept_bdwn:
        lines.append('Top Departments by Overrides:')
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('overrides', 0)} overrides "
                f"({item.get('override_rate_pct', 0.0):.1f}%)"
            )
    return '\n'.join(lines)


def _build_waste_context(signal):
    """Build context block for a WASTE (straight-to-bin) signal."""
    facts       = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    this_rate   = signal.get('this_week_stb_rate', 0.0)
    lines = [
        f"Alert Type: Waste (Straight-to-Bin)",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Straight-to-Bin Rate: {this_rate:.1f}%",
        f"This Week Waste Quantity: {signal.get('this_week_waste_qty', 0)}",
        f"This Week STB Quantity: {signal.get('this_week_stb_qty', 0)}",
        f"This Week Waste Value: \u00a3{signal.get('this_week_waste_value', 0.0):,.2f}",
    ]
    if signal.get('last_week_stb_rate') is not None:
        lines.append(f"Last Week STB Rate: {signal['last_week_stb_rate']:.1f}%")
    if signal.get('wow_change_pp') is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get('chain_stb_rate') is not None:
        lines.append(f"Chain Average STB Rate: {signal['chain_stb_rate']:.1f}%")
    if signal.get('above_chain_pp') is not None:
        lines.append(f"Above Chain Average By: {signal['above_chain_pp']:+.1f}pp")
    dept_bdwn = facts.get('waste_dept_breakdown', [])
    if dept_bdwn:
        lines.append('Top Departments by Waste:')
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('waste_qty', 0)} wasted units, "
                f"\u00a3{item.get('waste_value', 0.0):,.2f} "
                f"(waste rate {item.get('waste_rate_pct', 0.0):.1f}%)"
            )
    return '\n'.join(lines)


def _build_markdown_sellthrough_context(signal):
    """Build context block for a MARKDOWN_SELLTHROUGH signal."""
    facts       = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    this_rate   = signal.get('this_week_sellthrough_rate', 0.0)
    lines = [
        f"Alert Type: Markdown Sell-Through",
        f"Store: {store_label}",
        f"Triggers: {', '.join(signal.get('trigger_types', []))}",
        f"This Week Sell-Through Rate: {this_rate:.1f}%",
        f"This Week Markdown Quantity: {signal.get('this_week_markdown_qty', 0)}",
        f"This Week Markdown Value: \u00a3{signal.get('this_week_markdown_value', 0.0):,.2f}",
    ]
    if signal.get('last_week_sellthrough_rate') is not None:
        lines.append(f"Last Week Sell-Through Rate: {signal['last_week_sellthrough_rate']:.1f}%")
    if signal.get('wow_change_pp') is not None:
        lines.append(f"Week-on-Week Change: {signal['wow_change_pp']:+.1f}pp")
    if signal.get('chain_sellthrough_rate') is not None:
        lines.append(f"Chain Average Sell-Through Rate: {signal['chain_sellthrough_rate']:.1f}%")
    if signal.get('below_chain_pp') is not None:
        lines.append(f"Below Chain Average By: {signal['below_chain_pp']:.1f}pp")
    dept_bdwn = facts.get('sellthrough_dept_breakdown', [])
    if dept_bdwn:
        lines.append('Worst Departments by Sell-Through:')
        for item in dept_bdwn[:3]:
            lines.append(
                f"  {item.get('dept', '?')}: {item.get('sellthrough_rate_pct', 0.0):.1f}% "
                f"on {item.get('requested_qty', 0)} units"
            )
    return '\n'.join(lines)


def _build_markdown_sku_context(signal):
    """Build context block for a MARKDOWN_SKU (SKU-level markdown) signal."""
    facts       = signal.get('facts', {})
    store_label = signal.get('site_name') or f"Store {signal['store_id']}"
    item_desc   = signal.get('item_description') or f"Item {signal.get('item_id', '')}"
    req_count   = signal.get('markdown_request_count') or 0
    override    = signal.get('override_count')
    lbk_weeks   = signal.get('lookback_weeks', 4)
    lines = [
        f"Alert Type: SKU-Level Markdown",
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
    if signal.get('avg_markdown_pct') is not None:
        lines.append(f"Avg Markdown Depth: {signal['avg_markdown_pct']:.1f}%")
    history = facts.get('sku_markdown_history', [])
    if history:
        lines.append(f"Weekly History (last {len(history)} weeks):")
        for week in history:
            ov_str = f", {week['override_count']} overridden" if week.get('override_count') else ''
            lines.append(
                f"  w/c {week.get('week_start', '?')}: "
                f"{week.get('request_count', 0)} requests{ov_str}"
            )
    return '\n'.join(lines)


# Dispatch map used by _build_context. Declared after builders so all names
# resolve. Signal types not listed here fall through to _build_osa_context.
_CONTEXT_BUILDERS = {
    'COMPLIANCE':           _build_compliance_context,
    'OSA':                  _build_osa_context,
    'MARKDOWN_OVERRIDE':    _build_markdown_override_context,
    'WASTE':                _build_waste_context,
    'MARKDOWN_SELLTHROUGH': _build_markdown_sellthrough_context,
    'MARKDOWN_SKU':         _build_markdown_sku_context,
}


def generate(signal: dict, session) -> dict:
    """
    Generate narrative fields using Snowflake Cortex (mistral-large).

    Parameters
    ----------
    signal  : dict — output of enrich_signals (Stage 2), contains 'facts' key
    session : Snowpark Session

    Returns
    -------
    dict with keys: issue, explanation, cost_if_not_fixed, recommended_action
    Falls back to rule_based.generate on any failure.
    """
    card_skill = _load_card_skill()
    type_skill = _load_type_skill(signal.get('signal_type', ''))
    context    = _build_context(signal)

    skill_block = card_skill
    if type_skill:
        skill_block += f'\n\n--- INVESTIGATION SKILL ---\n{type_skill}\n--- END INVESTIGATION SKILL ---'

    prompt = (
        'You are a retail analyst writing content for a Smart Action Card for a store manager.\n'
        'Follow the Content Skill rules below exactly.\n\n'
        '--- CONTENT SKILL ---\n'
        f'{skill_block}\n'
        '--- END CONTENT SKILL ---\n\n'
        '--- SIGNAL DATA ---\n'
        f'{context}\n'
        '--- END SIGNAL DATA ---\n\n'
        'Using the Content Skill rules and the signal data above, return ONLY a JSON object '
        'with these four keys:\n'
        '  "issue"               \u2014 title slot\n'
        '  "explanation"         \u2014 summary sentence + worst day callout\n'
        '  "cost_if_not_fixed"   \u2014 cost panel sentence\n'
        '  "recommended_action"  \u2014 action panel (2\u20134 sentences)\n\n'
        'Do not include subclass contributor lists \u2014 those are rendered from structured data.\n'
        'Output raw JSON only. Do not wrap in markdown fences.'
    )

    prompt_escaped = prompt.replace("'", "''")

    try:
        result = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large', '{prompt_escaped}') AS RESPONSE"
        ).collect()
        raw = result[0]['RESPONSE'].strip()

        cleaned = _extract_json(raw)
        narrative = json.loads(cleaned)

        required = ['issue', 'explanation', 'cost_if_not_fixed', 'recommended_action']
        if all(k in narrative for k in required):
            return narrative

        _label = signal.get('department') or signal.get('signal_type', '?')
        print(
            f"[3_investigate/cortex] Missing fields for store {signal['store_id']} "
            f"{_label} — falling back to rule-based. "
            f"Keys received: {list(narrative.keys())}"
        )

    except json.JSONDecodeError as e:
        _label = signal.get('department') or signal.get('signal_type', '?')
        print(
            f"[3_investigate/cortex] Invalid JSON for store {signal['store_id']} "
            f"{_label}: {e} — falling back to rule-based."
        )
    except Exception as e:
        _label = signal.get('department') or signal.get('signal_type', '?')
        print(
            f"[3_investigate/cortex] Cortex error for store {signal['store_id']} "
            f"{_label}: {e} — falling back to rule-based."
        )

    return rule_based_generate(signal)
