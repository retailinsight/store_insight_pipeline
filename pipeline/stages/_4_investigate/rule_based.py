"""
Narrative Generator: Rule-Based Templates
==========================================
Produces the four alert card narrative fields from an enriched signal using
deterministic string templates.  No external dependencies — always produces
output, never fails.

This is the default narrative engine.  It is used directly by ``investigate.py``
and also serves as the fallback when ``cortex.py`` fails.

Extending
---------
To add new narrative logic for a different alert type (e.g. Waste), add
conditional branches in ``generate`` keyed on ``signal['trigger_types']`` or
a new ``alert_type`` field you add to the signal dict.

Public API
----------
    generate(signal: dict) -> dict
    Returns {issue, explanation, cost_if_not_fixed, recommended_action}
"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _trigger_summary(trigger_types, dept, signal):
    parts = []
    if "WOW" in trigger_types:
        drift = abs(signal.get("wow_drift_pp") or 0)
        parts.append(f"OSA dropped {drift:.1f}pp week-on-week")
    if "VS_CHAIN" in trigger_types:
        gap = abs(signal.get("chain_gap_pp") or 0)
        parts.append(f"OSA is {gap:.1f}pp below chain average")
    if "REPEAT" in trigger_types:
        n = signal.get("repeat_item_count") or 0
        parts.append(f"{n} item{'s' if n != 1 else ''} with persistent availability issues")
    if not parts:
        return f"{dept}: OSA alert"
    return f"{dept}: " + "; ".join(parts)


def _fmt_ppg_lines(items, header):
    if not items:
        return []
    lines = [f"{header}:"]
    for item in items:
        sign = "+" if item["lsv_change"] >= 0 else "-"
        abs_chg = abs(item["lsv_change"])
        lines.append(
            f"\u2022 {item['subclass_name']}: \u00a3{item['this_week_lsv']:,.2f} this week"
            f" (last week \u00a3{item['last_week_lsv']:,.2f}, {sign}\u00a3{abs_chg:,.2f})"
        )
    return lines


def _fmt_repeat_item_lines(repeat_items, top_n=3):
    if not repeat_items:
        return []
    lines = ["Items with persistent availability issues:"]
    for item in repeat_items[:top_n]:
        lines.append(
            f"\u2022 {item['ppg']} ({item['subclass']}): "
            f"triggered {item['alert_weeks']} weeks, "
            f"\u00a3{item['cumulative_lsv']:,.2f} cumulative lost sales"
        )
    return lines


def _fmt_dow_line(dow_pattern):
    if not dow_pattern:
        return []
    worst = dow_pattern[0]
    return [f"Worst day for lost sales this week: {worst['day']} (\u00a3{worst['lsv']:,.2f})"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _generate_tick_and_flick(signal: dict) -> dict:
    """Generate narrative for a TICK_AND_FLICK compliance alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    this_worked = signal.get("this_week_worked", 0)
    this_tf = signal.get("this_week_tf", 0)
    this_rate = signal.get("this_week_tf_rate", 0.0)
    last_worked = signal.get("last_week_worked", 0)
    last_tf = signal.get("last_week_tf", 0)
    last_rate = signal.get("last_week_tf_rate", 0.0)
    rate_change = signal.get("tf_rate_change", 0.0)
    chain_rate = signal.get("chain_tf_rate", 0.0)
    above_chain = signal.get("above_chain_by", 0.0)

    issue = f"{site_name}: tick-and-flick compliance declining"

    explanation_lines = [
        f"{this_tf} of {this_worked} alerts worked this week were tick-and-flick ({this_rate:.1f}%).",
        f"Tick-and-flick rate rose {rate_change:+.1f}pp week-on-week "
        f"(last week: {last_rate:.1f}%, {last_tf} of {last_worked} alerts).",
        f"Store tick-and-flick rate is {above_chain:.1f}pp above the chain average of {chain_rate:.1f}%.",
    ]

    cost_if_not_fixed = (
        "Unresolved alerts mean availability issues go unaddressed, "
        "increasing risk of lost sales across affected departments."
    )

    recommended_action = (
        f"Review alert working practice with colleagues at {site_name}. "
        f"Ensure alerts are being genuinely investigated before being closed \u2014 "
        f"spot-check the alert types above. "
        f"Consider a coaching session with the store manager on accurate alert feedback."
    )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost_if_not_fixed,
        "recommended_action": recommended_action,
    }


def _generate_markdown_override(signal: dict) -> dict:
    """Generate narrative for a MARKDOWN_OVERRIDE alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    this_rate = signal.get("this_week_override_rate", 0.0)
    last_rate = signal.get("last_week_override_rate")
    wow_change = signal.get("wow_change_pp")
    chain_rate = signal.get("chain_override_rate")
    above_chain = signal.get("above_chain_pp")
    total_mds = signal.get("this_week_total_markdowns", 0)
    overrides = signal.get("this_week_overrides", 0)

    facts = signal.get("facts", {})
    dept_bdwn = [
        row
        for row in facts.get("override_dept_breakdown", [])
        if str(row.get("dept") or "").strip().lower() not in {"", "unknown", "none", "nan"}
    ]

    if "VS_CHAIN" in triggers and above_chain is not None:
        issue = f"{site_name}: markdown override rate {this_rate:.1f}% — {above_chain:.1f}pp above chain average"
    elif "WOW" in triggers and wow_change is not None:
        issue = f"{site_name}: markdown override rate up {wow_change:.1f}pp this week to {this_rate:.1f}%"
    else:
        issue = f"{site_name}: elevated markdown override rate ({this_rate:.1f}%)"

    explanation_lines = [
        f"{overrides} of {total_mds} markdowns were overridden this week ({this_rate:.1f}%).",
    ]
    if "VS_CHAIN" in triggers and chain_rate is not None:
        explanation_lines.append(
            f"Chain average is {chain_rate:.1f}% — this store is {above_chain:.1f}pp above."
        )
    if "WOW" in triggers and last_rate is not None:
        explanation_lines.append(
            f"Last week the override rate was {last_rate:.1f}% — up {wow_change:.1f}pp."
        )
    if dept_bdwn:
        top = dept_bdwn[0]
        explanation_lines.append(
            f"Top department: {top['dept']} ({top['overrides']} overrides, {top['override_rate_pct']:.1f}%)."
        )

    top_dept = dept_bdwn[0]["dept"] if dept_bdwn else None
    action = (
        f"Review override decisions{f' in {top_dept}' if top_dept else ''} with the store manager. "
        "Ensure markdown guidance is followed — overrides should only be made where there is a clear commercial reason."
    )

    cost = (
        "Items overridden at a higher price are at increased risk of reaching end-of-life unsold, "
        "driving unnecessary waste."
    )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost,
        "recommended_action": action,
    }


def _generate_waste(signal: dict) -> dict:
    """Generate narrative for a WASTE alert."""
    site_name   = signal.get('site_name') or f'Store {signal["store_id"]}'
    triggers    = signal.get('trigger_types', [])
    this_rate   = signal.get('this_week_stb_rate', 0.0)
    last_rate   = signal.get('last_week_stb_rate')
    wow_change  = signal.get('wow_change_pp')
    chain_rate  = signal.get('chain_stb_rate')
    above_chain = signal.get('above_chain_pp')
    waste_qty   = signal.get('this_week_waste_qty', 0)
    waste_val   = signal.get('this_week_waste_value', 0.0)

    facts = signal.get("facts", {})
    dept_bdwn = [
        row
        for row in facts.get("waste_dept_breakdown", [])
        if str(row.get("dept") or "").strip().lower() not in {"", "unknown", "none", "nan"}
    ]

    if 'VS_CHAIN' in triggers and above_chain is not None:
        issue = f'{site_name}: waste-to-markdown ratio {this_rate:.1f}% — {above_chain:.1f}pp above chain average'
    elif 'WOW' in triggers and wow_change is not None:
        issue = f'{site_name}: waste-to-markdown ratio up {wow_change:.1f}pp this week to {this_rate:.1f}%'
    else:
        issue = f'{site_name}: elevated waste-to-markdown ratio ({this_rate:.1f}%)'

    explanation_lines = [
        f'{waste_qty} units were wasted this week, valued at £{waste_val:,.2f} at original price.',
        f'Waste was {this_rate:.1f}% of markdown volume this week.',
    ]
    if "VS_CHAIN" in triggers and chain_rate is not None:
        explanation_lines.append(
            f'Chain average waste-to-markdown ratio is {chain_rate:.1f}% — this store is {above_chain:.1f}pp above.'
        )
    if "WOW" in triggers and last_rate is not None:
        explanation_lines.append(
            f'Last week the waste-to-markdown ratio was {last_rate:.1f}% — up {wow_change:.1f}pp.'
        )
    if dept_bdwn:
        top = dept_bdwn[0]
        explanation_lines.append(
            f"Top department: {top['dept']} ({top['waste_qty']} wasted units, \u00a3{top['waste_value']:,.2f})."
        )

    top_dept = dept_bdwn[0]["dept"] if dept_bdwn else None
    action = (
        f'Review waste and markdown processes{f" in {top_dept}" if top_dept else ""}. '
        'Assess markdown timing, markdown depth, ordering, and operational handling to identify opportunities to reduce waste.'
    )

    cost = (
        f'Items worth approximately \u00a3{waste_val:,.2f} at original price were wasted this week. '
        'Review whether some could have been recovered through earlier markdown action.'
    )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost,
        "recommended_action": action,
    }


def _generate_markdown_sellthrough(signal: dict) -> dict:
    """Generate narrative for a MARKDOWN_SELLTHROUGH alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    this_rate = signal.get("this_week_sellthrough_rate", 0.0)
    last_rate = signal.get("last_week_sellthrough_rate")
    wow_change = signal.get("wow_change_pp")
    chain_rate = signal.get("chain_sellthrough_rate")
    below_chain = signal.get("below_chain_pp")
    md_qty = signal.get("this_week_markdown_qty", 0)
    md_value = signal.get("this_week_markdown_value", 0.0)

    facts = signal.get("facts", {})
    dept_bdwn = [
        row
        for row in facts.get("sellthrough_dept_breakdown", [])
        if str(row.get("dept") or "").strip().lower() not in {"", "unknown", "none", "nan"}
    ]

    if "VS_CHAIN" in triggers and below_chain is not None:
        issue = f"{site_name}: markdown sell-through {this_rate:.1f}% — {below_chain:.1f}pp below chain average"
    elif "WOW" in triggers and wow_change is not None:
        issue = f"{site_name}: markdown sell-through dropped {abs(wow_change or 0):.1f}pp to {this_rate:.1f}%"
    else:
        issue = f"{site_name}: low markdown sell-through rate ({this_rate:.1f}%)"

    explanation_lines = [
        f"Of {md_qty} markdown units, {this_rate:.1f}% were sold, generating \u00a3{md_value:,.2f} in markdown revenue.",
    ]
    if "VS_CHAIN" in triggers and chain_rate is not None:
        explanation_lines.append(
            f"Chain average sell-through is {chain_rate:.1f}% — this store is {below_chain:.1f}pp below."
        )
    if "WOW" in triggers and last_rate is not None:
        explanation_lines.append(
            f"Last week sell-through was {last_rate:.1f}% — down {abs(wow_change or 0):.1f}pp."
        )
    if dept_bdwn:
        worst = dept_bdwn[0]
        explanation_lines.append(
            f'Worst department: {worst["dept"]} ({worst["sellthrough_rate_pct"]:.1f}% sell-through on {worst["total_qty"]} units).'
        )

    worst_dept = dept_bdwn[0]["dept"] if dept_bdwn else None
    action = (
        f"Review markdown depth and product placement{f' in {worst_dept}' if worst_dept else ''}. "
        "Consider whether prices are being reduced far enough to drive customer uptake. "
        "Ensure marked-down items are clearly signed and prominently positioned."
    )

    cost = (
        f"Items not sold at markdown will progress to waste. With a {this_rate:.1f}% sell-through rate "
        f"and {md_qty} units in the markdown programme, there is significant waste exposure "
        "if sell-through does not improve."
    )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost,
        "recommended_action": action,
    }


def _generate_markdown_sku(signal: dict) -> dict:
    """Generate narrative for a MARKDOWN_SKU alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    item_desc = signal.get("item_description") or f"Item {signal.get('item_id', '')}"
    department = signal.get("department", "")
    req_count = signal.get("markdown_request_count") or 0
    override_cnt = signal.get("override_count")
    lbk_weeks = signal.get("lookback_weeks", 4)
    avg_pct = signal.get("avg_markdown_pct")

    facts = signal.get("facts", {})
    history = facts.get("sku_markdown_history", [])

    if "REPEAT_REQUEST" in triggers and "EXCESSIVE_OVERRIDE" in triggers:
        issue = f"{site_name}: {item_desc} — repeat markdown requests and excessive overrides over {lbk_weeks} weeks"
    elif "EXCESSIVE_OVERRIDE" in triggers and override_cnt is not None:
        override_rate = round(override_cnt / req_count * 100) if req_count else 0
        issue = f"{site_name}: {item_desc} overridden {override_cnt} of {req_count} requests ({override_rate}%) in {lbk_weeks} weeks"
    else:
        issue = f"{site_name}: {item_desc} marked down {req_count} times in {lbk_weeks} weeks"

    explanation_lines = [f"{item_desc} ({department})."]

    if "REPEAT_REQUEST" in triggers:
        avg_str = f", avg markdown depth {avg_pct:.1f}%" if avg_pct is not None else ""
        explanation_lines.append(
            f"This item has been flagged for markdown on {req_count} occasions "
            f"over the last {lbk_weeks} weeks{avg_str}."
        )

    if "EXCESSIVE_OVERRIDE" in triggers and override_cnt is not None:
        override_rate = round(override_cnt / req_count * 100) if req_count else 0
        explanation_lines.append(
            f"The markdown recommendation has been overridden {override_cnt} of {req_count} times "
            f"— a {override_rate}% override rate."
        )

    if history:
        explanation_lines.append(f"Weekly history (last {len(history)} weeks):")
        for week in history:
            ov_str = f", {week['override_count']} overridden" if week.get("override_count") else ""
            explanation_lines.append(
                f"\u2022 w/c {week['week_start']}: {week['request_count']} requests{ov_str}"
            )

    if "REPEAT_REQUEST" in triggers:
        action = (
            f"Review ordering and ranging for {item_desc} in {department}. "
            "Consider whether this item suits this store's customer profile or whether order quantities should be reduced."
        )
        cost = (
            "An item requiring markdown every week represents a recurring ordering cost and waste risk. "
            "If quantities are not adjusted, this pattern is likely to continue."
        )
    else:
        action = (
            f"Discuss the pricing guidance for {item_desc} with the store manager. "
            "If the algorithm recommendation is consistently wrong for this item, escalate to the buying team."
        )
        cost = (
            "Consistently overriding the recommended markdown means this item is likely to sell at a slower rate, "
            "increasing its risk of reaching end-of-life unsold."
        )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost,
        "recommended_action": action,
    }


def _generate_osa_recurring_slot(signal: dict) -> dict:
    """Generate narrative for an OSA_RECURRING_SLOT alert."""
    site_name      = signal.get('site_name') or f"Store {signal['store_id']}"
    dept           = signal['department']
    dow_name       = signal.get('dow_name', 'Unknown day')
    period_label   = signal.get('period_label', 'Unknown period')
    n_items        = signal.get('repeat_item_count', 0)
    total_lsv      = signal.get('total_lsv', 0.0)
    avg_weekly_lsv = signal.get('avg_weekly_lsv', 0.0)
    item_details   = signal.get('repeat_item_details', [])

    facts = signal.get('facts', {})
    slot_share = facts.get('recurring_slot_share_pct')
    dept_share = facts.get('slot_share_of_dept_total_pct')
    trend      = facts.get('slot_trend', 'flat')
    history    = facts.get('slot_history', [])

    issue = (
        f'{site_name}: {dept} has recurring lost sales on {dow_name} {period_label}'
    )

    explanation_lines = [
        f'{n_items} item{"s" if n_items != 1 else ""} repeatedly lost sales '
        f'in the {period_label} slot on {dow_name}s, '
        f'with a total lost sales value of \u00a3{total_lsv:,.2f} across the lookback window.',
        f'Average weekly lost sales for this slot: \u00a3{avg_weekly_lsv:,.2f}.',
    ]

    if slot_share is not None:
        explanation_lines.append(
            f'These recurring items account for {slot_share:.1f}% of lost sales '
            f'in this {dow_name} {period_label} slot.'
        )
    if dept_share is not None:
        explanation_lines.append(
            f'This slot accounts for {dept_share:.1f}% of total lost sales in {dept}.'
        )
    if trend != 'flat':
        explanation_lines.append(f'The slot lost-sales trend is {trend}.')

    if item_details:
        explanation_lines.append('Top recurring items:')
        for item in item_details[:5]:
            desc = item.get('item_description')
            item_label = f'{desc} ({item["item_code"]})' if desc else item['item_code']
            explanation_lines.append(
                f'\u2022 {item_label}: '
                f'\u00a3{item["total_lsv"]:,.2f} over {item["repeat_weeks"]} week{"s" if item["repeat_weeks"] != 1 else ""}'
            )

    if history:
        explanation_lines.append(f'Weekly slot history (last {len(history)} matched weeks):')
        for week in history[-5:]:
            explanation_lines.append(
                f'\u2022 {week["year"]}-W{week["week"]}: '
                f'\u00a3{week["lsv"]:,.2f} LSV ({week["osa_pct"]:.1f}% OSA)'
            )

    explanation = '\n'.join(explanation_lines)

    projection_weeks = facts.get('projection_weeks') or signal.get('projection_weeks') or 4
    cost_projection = (
        signal.get('projected_cost')
        or round(avg_weekly_lsv * projection_weeks, 2)
    )

    cost = (
        f'If this recurring slot problem continues, the store could lose approximately '
        f'\u00a3{cost_projection:,.2f} over the next {projection_weeks} weeks.'
    )

    action = (
        f'Investigate operational drivers behind {dow_name} {period_label} shortages in {dept}. '
        'Check delivery schedules, shelf-filling routines, staffing levels, and demand spikes '
        'for the flagged items.'
    )

    return {
        'issue':              issue,
        'explanation':        explanation,
        'cost_if_not_fixed':  cost,
        'recommended_action': action,
    }


def _generate_waste_trim(signal: dict) -> dict:
    """Generate narrative for a WASTE_TRIM alert."""
    site_name        = signal.get('site_name') or f"Store {signal['store_id']}"
    item_desc        = signal.get('item_description') or f"Item {signal['item_id']}"
    department       = signal.get('department', '')
    markdown_units   = signal.get('markdown_units', 0)
    total_units      = signal.get('total_units', 0)
    markdown_ratio   = signal.get('markdown_ratio', 0.0)
    markdown_value   = signal.get('markdown_value', 0.0)
    projected_cost   = signal.get('projected_cost', markdown_value)

    facts = signal.get('facts', {})
    chain_ratio = facts.get('chain_markdown_ratio')
    dept_ratio  = facts.get('dept_markdown_ratio')
    trend       = facts.get('weekly_trend', [])

    issue = (
        f'{site_name}: {item_desc} in {department} sold '
        f'{markdown_ratio:.1%} of its units at markdown this week'
    )

    explanation_lines = [
        f'{markdown_units} of {total_units} units sold were at markdown '
        f'(£{markdown_value:,.2f} markdown sales).',
    ]

    if chain_ratio is not None:
        explanation_lines.append(
            f'Across all stores, this item had {chain_ratio:.1%} markdown sales.'
        )
    if dept_ratio is not None:
        explanation_lines.append(
            f'The {department} department averaged {dept_ratio:.1%} markdown sales this week.'
        )

    if trend:
        explanation_lines.append('Weekly markdown ratio trend:')
        for week in trend[-4:]:
            explanation_lines.append(
                f'\u2022 w/c {week["week_start"]}: '
                f'{week["markdown_units"]:.0f}/{week["total_units"]:.0f} units '
                f'({week["ratio"]:.1%})'
            )

    cost = (
        f'If this item continues to rely on markdown clearance, it risks losing '
        f'approximately £{projected_cost:,.2f} in full-price sales potential each week.'
    )

    action = (
        f'Review ranging and ordering for {item_desc} in {department}. '
        'Check whether demand forecasting is overestimating sales or whether the store '
        'is receiving excess stock that can only clear at markdown.'
    )

    return {
        'issue':              issue,
        'explanation':        '\n'.join(explanation_lines),
        'cost_if_not_fixed':  cost,
        'recommended_action': action,
    }


def generate(signal: dict) -> dict:
    """
    Generate narrative fields for a single enriched signal using templates.

    Parameters
    ----------
    signal : dict — output of enrich_signals (Stage 2), contains 'facts' key

    Returns
    -------
    dict with keys: issue, explanation, cost_if_not_fixed, recommended_action
    """
    triggers = signal["trigger_types"]

    if "TICK_AND_FLICK" in triggers:
        return _generate_tick_and_flick(signal)

    signal_type = signal.get("signal_type", "")

    if signal_type == "MARKDOWN_OVERRIDE":
        return _generate_markdown_override(signal)

    if signal_type == "WASTE":
        return _generate_waste(signal)

    if signal_type == "MARKDOWN_SELLTHROUGH":
        return _generate_markdown_sellthrough(signal)

    if signal_type == "MARKDOWN_SKU":
        return _generate_markdown_sku(signal)

    if signal_type == 'OSA_RECURRING_SLOT':
        return _generate_osa_recurring_slot(signal)

    if signal_type == 'WASTE_TRIM':
        return _generate_waste_trim(signal)

    dept     = signal['department']
    facts    = signal['facts']

    lsv = signal.get("this_week_lsv") or 0
    this_week_osa = signal.get("this_week_osa")
    last_week_osa = signal.get("last_week_osa")
    wow_drift = signal.get("wow_drift_pp")
    chain_osa = facts.get("chain_this_week_osa") or signal.get("chain_this_week_osa")
    chain_gap = signal.get("chain_gap_pp")
    chain_drift = facts.get("chain_drift_pp")
    cost_projection = facts["cost_projection"]
    proj_weeks = facts["projection_weeks"]

    issue = _trigger_summary(triggers, dept, signal)

    explanation_lines = []

    explanation_lines.append(f"There has been \u00a3{lsv:,.2f} of lost sales in {dept} this week.")

    if "WOW" in triggers and this_week_osa is not None and last_week_osa is not None:
        chain_drift_str = f" (chain moved {chain_drift:+.1f}pp)" if chain_drift is not None else ""
        explanation_lines.append(
            f"Store OSA dropped {abs(wow_drift or 0):.1f}pp to {this_week_osa:.1f}%"
            f"{chain_drift_str}."
        )

    if "VS_CHAIN" in triggers and this_week_osa is not None and chain_osa is not None:
        explanation_lines.append(
            f"Store OSA this week is {this_week_osa:.1f}%, vs chain average of {chain_osa:.1f}%"
            f" ({abs(chain_gap or 0):.1f}pp gap)."
        )

    if "REPEAT" in triggers:
        n = signal.get("repeat_item_count") or 0
        explanation_lines.append(
            f"{n} item{'s' if n != 1 else ''} in {dept} "
            f"{'have' if n != 1 else 'has'} triggered repeated availability alerts "
            f"over the last 10 weeks."
        )
        explanation_lines += _fmt_repeat_item_lines(signal.get("repeat_item_details", []))

    explanation_lines += _fmt_ppg_lines(
        facts["subclass_contributors"], "Biggest lost sales contributors this week"
    )
    explanation_lines += _fmt_ppg_lines(
        facts["subclass_changes"], "Biggest week-on-week increase in lost sales"
    )
    explanation_lines += _fmt_dow_line(facts["dow_pattern"])

    explanation = "\n".join(explanation_lines)

    cost_if_not_fixed = (
        f"If this continues at the same rate, the store could lose approximately "
        f"\u00a3{cost_projection:,.2f} in the next {proj_weeks} weeks."
    )

    action_parts = [f"Review availability in {dept} daily."]
    if "WOW" in triggers or "VS_CHAIN" in triggers:
        action_parts.append(
            "Ensure replenishment orders are raised before 8am and all gaps on "
            "high-velocity lines are filled before the store opens."
        )
    if "REPEAT" in triggers:
        action_parts.append(
            "Investigate root cause of repeated OOS items \u2014 review replenishment "
            "parameters, supplier lead times, and on-shelf capacity."
        )
    if facts.get("worst_day"):
        action_parts.append(
            f"Pay particular attention on {facts['worst_day']['day']}s, "
            f"the worst day for lost sales this week."
        )

    recommended_action = " ".join(action_parts)

    return {
        "issue": issue,
        "explanation": explanation,
        "cost_if_not_fixed": cost_if_not_fixed,
        "recommended_action": recommended_action,
    }
