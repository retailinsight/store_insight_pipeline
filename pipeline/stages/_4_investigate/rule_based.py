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


def _fmt_lsv_composition_lines(composition):
    """Return a one-line composition sentence for the OSA explanation."""
    if not composition:
        return []
    buckets = composition.get("buckets", {})
    active = []
    for key, label in (("store_process", "store process"), ("upstream", "upstream")):
        bucket = buckets.get(key)
        if bucket and bucket.get("lsv", 0) > 0:
            active.append((bucket["pct"], label, bucket["lsv"]))
    if not active:
        return []
    active.sort(reverse=True)
    parts = [f"{label} ({pct:.0f}%, \u00a3{lsv:,.2f})" for pct, label, lsv in active]
    if len(parts) == 1:
        return [f"The lost sales are driven entirely by {parts[0]}."]
    return [f"The lost sales are driven by {', '.join(parts)}."]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _generate_tick_and_flick(signal: dict) -> dict:
    """Generate narrative for a TICK_AND_FLICK compliance alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    this_worked = signal.get("this_week_worked", 0)
    this_tf = signal.get("this_week_tf", 0)
    this_rate = signal.get("this_week_tf_rate", 0.0)
    last_worked = signal.get("last_week_worked", 0)
    last_tf = signal.get("last_week_tf", 0)
    last_rate = signal.get("last_week_tf_rate", 0.0)
    rate_change = signal.get("tf_rate_change", 0.0)
    chain_rate = signal.get("chain_tf_rate", 0.0)
    above_chain = signal.get("above_chain_by", 0.0)
    projected_cost = signal.get("projected_cost", 0.0) or 0.0
    workload = signal.get("workload", {}) or {}
    volume_classification = workload.get("volume_classification", "STABLE")
    volume_change_pct = workload.get("volume_change_pct", 0.0)
    facts = signal.get("facts", {})
    driver = facts.get("driver_assessment", {}) or {}
    likely_driver = driver.get("likely_driver", "COACHING")

    include_wow = "WOW" in triggers or "TICK_AND_FLICK" in triggers
    include_vs_chain = "VS_CHAIN" in triggers or "TICK_AND_FLICK" in triggers

    if "WOW" in triggers and "VS_CHAIN" in triggers:
        issue = (
            f"{site_name}: tick-and-flick rate {this_rate:.1f}% — "
            f"{above_chain:.1f}pp above chain average and up {rate_change:.1f}pp week-on-week"
        )
    elif "VS_CHAIN" in triggers:
        issue = (
            f"{site_name}: tick-and-flick rate {this_rate:.1f}% — "
            f"{above_chain:.1f}pp above chain average"
        )
    elif "WOW" in triggers:
        issue = f"{site_name}: tick-and-flick rate up {rate_change:.1f}pp this week to {this_rate:.1f}%"
    else:
        issue = f"{site_name}: tick-and-flick compliance declining"

    explanation_lines = [
        f"{this_tf} of {this_worked} alerts worked this week were tick-and-flick ({this_rate:.1f}%).",
        f"Alert volume is {volume_classification.lower()} ({volume_change_pct:+.1f}% week-on-week).",
    ]
    if include_wow:
        explanation_lines.insert(
            1,
            f"Tick-and-flick rate rose {rate_change:+.1f}pp week-on-week "
            f"(last week: {last_rate:.1f}%, {last_tf} of {last_worked} alerts).",
        )
    if include_vs_chain:
        explanation_lines.insert(
            len(explanation_lines) - 1,
            f"Store tick-and-flick rate is {above_chain:.1f}pp above the chain average of {chain_rate:.1f}%.",
        )

    cost_if_not_fixed = f"\u00a3{projected_cost:,.2f} per week if not fixed."

    if likely_driver == "WORKLOAD":
        recommended_action = (
            f"Alert volume is up {volume_change_pct:.0f}% and alerts are being ticked without being worked. "
            f"Area manager to review staffing and alert workload with the store manager at {site_name} "
            f"this week before treating this as a compliance issue. "
            f"Review in 7 days against a tick-and-flick rate of {last_rate:.2f}%."
        )
    else:
        recommended_action = (
            f"Alert volume is broadly unchanged, so the rise in tick and flick is not explained by workload. "
            f"Area manager to discuss alert working with the store manager at {site_name} this week. "
            f"Review in 7 days against a tick-and-flick rate of {last_rate:.2f}%."
        )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost_if_not_fixed,
        "recommended_action": recommended_action,
    }


def _generate_markdown_override(signal: dict) -> dict:
    """Generate narrative for a MARKDOWN_OVERRIDE alert."""
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

    if chain_rate is None:
        chain_str = None
    elif chain_rate < 1:
        chain_str = 'under 1%'
    else:
        chain_str = f'{chain_rate:.1f}%'

    if dept_bdwn:
        top = dept_bdwn[0]
        issue = f'Coach your team on override decisions in {top["dept"]}.'
        action = (
            f'{top["overrides"]} of {overrides} overrides this week came from this department'
            + (f', against a chain average override rate of {chain_str}.' if chain_str else '.')
        )
    else:
        issue = 'Coach your team on override decisions.'
        action = (
            f'{overrides} of {total_mds} markdowns were overridden this week ({this_rate:.1f}%)'
            + (f', against a chain average of {chain_str}.' if chain_str else '.')
        )

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
    triggers = signal.get("trigger_types", [])
    item_desc = signal.get("item_description") or f"Item {signal.get('item_id', '')}"
    department = signal.get("department", "")
    req_count = signal.get("markdown_request_count") or 0
    override_cnt = signal.get("override_count")
    lbk_weeks = signal.get("lookback_weeks", 4)
    avg_pct = signal.get("avg_markdown_pct")

    facts = signal.get("facts", {})
    history = facts.get("sku_markdown_history", [])

    item = _clean_item_name(signal.get("item_description")) or "this item"
    dept = department
    req = req_count
    lbk = lbk_weeks
    ov = override_cnt

    if "REPEAT_REQUEST" in triggers:
        issue = f'Check your order quantity for {item} in {dept}.'
        sentence = f'It has been marked down {req} times in the last {lbk} weeks'
        depth = f' at an average depth of {avg_pct:.0f}%' if avg_pct is not None else ''
        subtitle = sentence + depth + ' — reducing the order should cut waste and protect margin.'
        if "EXCESSIVE_OVERRIDE" in triggers and ov is not None:
            subtitle += f' The markdown recommendation was also overridden {ov} of {req} times.'
    else:
        issue = f'Review the markdown price for {item} in {dept}.'
        if ov is not None:
            subtitle = f'The recommended markdown was overridden {ov} of {req} times in the last {lbk} weeks.'
        else:
            subtitle = f'The recommended markdown has been repeatedly overridden in the last {lbk} weeks.'

    explanation_lines = [f"{_clean_item_name(item_desc)} ({department})."]

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
        cost = (
            "An item requiring markdown every week represents a recurring ordering cost and waste risk. "
            "If quantities are not adjusted, this pattern is likely to continue."
        )
    else:
        cost = (
            "Consistently overriding the recommended markdown means this item is likely to sell at a slower rate, "
            "increasing its risk of reaching end-of-life unsold."
        )

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost,
        "recommended_action": subtitle,
    }


def _generate_osa_recurring_slot(signal: dict) -> dict:
    """Generate narrative for an OSA_RECURRING_SLOT alert."""
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

    period_word = {1: 'morning', 2: 'afternoon', 3: 'evening'}.get(signal.get('period_id'))
    if period_word is None:
        period_word = period_label.split(' (')[0].lower()

    focus_labels = []
    for detail in item_details[:3]:
        label = _clean_item_name(detail.get('item_description'))
        if label:
            focus_labels.append(label)
    if len(focus_labels) <= 1:
        joined = focus_labels[0] if focus_labels else ''
    elif len(focus_labels) == 2:
        joined = f'{focus_labels[0]} and {focus_labels[1]}'
    else:
        joined = f'{focus_labels[0]}, {focus_labels[1]}, and {focus_labels[2]}'
    focus = f' — focus on {joined}' if joined else ''

    issue = f'Check {dow_name} {period_word} availability in {dept}{focus}.'

    weeks = len(history)
    if not weeks:
        weeks = max((d.get('repeat_weeks') or 0) for d in item_details) if item_details else 0

    window_phrase = f'over the last {weeks} weeks' if weeks else 'in recent weeks'
    explanation_lines = [
        f'{n_items} item{"s" if n_items != 1 else ""} repeatedly lost sales '
        f'in the {period_label} slot on {dow_name}s, '
        f'with a total lost sales value of \u00a3{total_lsv:,.2f} {window_phrase}.',
        f'When these lines run short they lose about \u00a3{avg_weekly_lsv:,.2f} a week between them.',
    ]

    if history:
        slot_avg = sum(h["lsv"] for h in history) / len(history)
        explanation_lines.append(
            f'Across all lines, this slot averages \u00a3{slot_avg:,.2f} a week in lost sales.'
        )

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
            item_label = _clean_item_name(item.get('item_description')) or 'Unnamed item'
            explanation_lines.append(
                f'\u2022 {item_label}: '
                f'\u00a3{item["total_lsv"]:,.2f} over {item["repeat_weeks"]} week{"s" if item["repeat_weeks"] != 1 else ""}'
            )

    if history:
        explanation_lines.append(f'Weekly slot history (all lines, last {min(5, len(history))} of {len(history)} weeks):')
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
        f'If these lines keep running short in this slot, the store could lose approximately '
        f'\u00a3{cost_projection:,.2f} over the next {projection_weeks} weeks.'
    )

    noun = 'line has' if n_items == 1 else 'lines have'
    if weeks:
        action = (
            f'{n_items} {noun} run short repeatedly in this slot over the last {weeks} weeks.'
        )
    else:
        action = (
            f'{n_items} {noun} run short repeatedly in this slot in recent weeks.'
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


_PERIOD_WORDS = {1: 'mornings', 2: 'afternoons', 3: 'evenings'}


def _clean_item_name(name) -> str:
    """Tidy raw source item descriptions: collapse runs of whitespace and drop trailing '#'."""
    text = ' '.join(str(name or '').split())
    return text.rstrip('# ').strip()


def _osa_actionable_title(signal: dict) -> str:
    """Action-first card title shared by OSA_STORE_ACTIONABLE and OSA_BIG_DROP."""
    dept = signal['department']
    facts = signal.get('facts') or {}
    slot = facts.get('worst_day_period') or {}
    day = slot.get('day')
    period_word = _PERIOD_WORDS.get(slot.get('period_id'))
    if day and period_word:
        return f'Give replenishment in {dept} extra attention on {day} {period_word}.'
    if not day:
        day = (facts.get('worst_day') or {}).get('day')
    if day:
        return f'Give replenishment in {dept} extra attention on {day}s.'
    return f'Give replenishment in {dept} extra attention this week.'


def _osa_leading_ppg_name(facts: dict):
    ppgs = facts.get('ppg_lsv_changes') or facts.get('ppg_contributors') or []
    if not ppgs:
        return None
    ppg = ppgs[0]
    return ppg.get('ppg') or ppg.get('ppg_name') or ppg.get('name')


def _osa_actionable_cost(facts: dict, store_lsv: float) -> str:
    projection = facts.get('cost_projection') or {}
    weeks = int(projection.get('projection_weeks') or facts.get('projection_weeks') or 4)
    cost = float(projection.get('store_controlled_cost_of_inaction') or store_lsv * weeks)
    return (
        f'If this continues at the same rate, store-controlled lost sales could cost '
        f'approximately £{cost:,.2f} over the next {weeks} weeks.'
    )


def _generate_osa_store_actionable(signal: dict) -> dict:
    dept = signal['department']
    facts = signal.get('facts') or {}
    lsv = signal.get('this_week_lsv') or {}
    store_lsv = float(lsv.get('store_controlled') or 0)

    issue = _osa_actionable_title(signal)

    this_osa = signal.get('this_week_osa')
    last_osa = signal.get('last_week_osa')
    chain_osa = signal.get('chain_this_week_osa')
    if chain_osa is None:
        chain_osa = facts.get('chain_store_this_week_osa')

    explanation = []
    dropped = last_osa is not None and this_osa is not None and this_osa < last_osa
    if dropped and chain_osa is not None:
        explanation.append(
            f'Store-controlled OSCA in {dept} has dropped to {this_osa:.1f}% in the '
            f'last 7 days compared with {last_osa:.1f}% in the week before, and a '
            f'Society average of {chain_osa:.1f}%.'
        )
    elif dropped:
        explanation.append(
            f'Store-controlled OSCA in {dept} has dropped to {this_osa:.1f}% in the '
            f'last 7 days compared with {last_osa:.1f}% in the week before.'
        )
    elif this_osa is not None and chain_osa is not None:
        explanation.append(
            f'Store-controlled OSCA in {dept} was {this_osa:.1f}% in the last 7 days '
            f'against a Society average of {chain_osa:.1f}%.'
        )
    elif this_osa is not None:
        explanation.append(
            f'Store-controlled OSCA in {dept} was {this_osa:.1f}% in the last 7 days.'
        )
    else:
        explanation.append(
            f'{dept} recorded £{store_lsv:,.2f} of store-controlled lost sales in the last 7 days.'
        )

    ppg_name = _osa_leading_ppg_name(facts)
    if ppg_name:
        explanation.append(f'{ppg_name} is the worst performing PPG.')

    subtitle = explanation[0]
    if ppg_name:
        subtitle += f' {ppg_name} is the worst performing PPG.'

    return {
        'issue': issue,
        'explanation': '\n'.join(explanation),
        'cost_if_not_fixed': _osa_actionable_cost(facts, store_lsv),
        'recommended_action': subtitle,
    }


def _generate_osa_big_drop(signal: dict) -> dict:
    """Narrative for an OSA_BIG_DROP day-on-day alert.

    Shares the actionable title with OSA_STORE_ACTIONABLE but keeps the
    multi-line explanation view, naming the two trading days compared.
    """
    dept = signal['department']
    facts = signal.get('facts') or {}
    lsv = signal.get('this_week_lsv') or {}
    store_lsv = float(lsv.get('store_controlled') or 0)
    drift = abs(float(signal.get('wow_drift_pp') or 0))

    issue = _osa_actionable_title(signal)

    explanation = []
    last_osa = signal.get('last_week_osa')
    this_osa = signal.get('this_week_osa')
    prior_day = signal.get('prior_day')
    latest_day = signal.get('latest_day')
    day_word = latest_day or 'that day'
    if last_osa is not None and this_osa is not None:
        if prior_day and latest_day:
            drop_sentence = (
                f'Store-controlled OSCA in {dept} dropped {drift:.1f}pp in a single '
                f'day — from {last_osa:.1f}% on {prior_day} to {this_osa:.1f}% on {latest_day}.'
            )
        else:
            drop_sentence = (
                f'Store-controlled OSCA in {dept} dropped {drift:.1f}pp in a single '
                f'day — from {last_osa:.1f}% to {this_osa:.1f}%.'
            )
        explanation.append(drop_sentence)
    else:
        drop_sentence = (
            f'{dept} recorded £{store_lsv:,.2f} of lost sales in a single day '
            f'while recorded inventory was positive.'
        )
    explanation.append(
        f'The department had £{store_lsv:,.2f} of lost sales on {day_word} while recorded inventory was positive.'
    )

    ppgs = facts.get('ppg_lsv_changes') or facts.get('ppg_contributors') or []
    if ppgs:
        ppg = ppgs[0]
        name = ppg.get('ppg') or ppg.get('ppg_name') or ppg.get('name')
        value = (ppg.get('latest_week_lsv') or {}).get('store_controlled', 0)
        explanation.append(f'Over the last 7 days the leading PPG was {name} (£{value:,.2f} store-controlled lost sales).')

    items = facts.get('item_lsv_changes') or []
    if items:
        item = items[0]
        name = _clean_item_name(item.get('item_name')) or item.get('item_code')
        latest = float((item.get('latest_week_lsv') or {}).get('store_controlled') or 0)
        prior = float((item.get('prior_week_lsv') or {}).get('store_controlled') or 0)
        explanation.append(
            f"The largest item offender over the last 7 days was {name} "
            f"with £{latest:,.2f} of store-controlled lost sales (£{prior:,.2f} the week before)."
        )

    projection = facts.get('cost_projection') or {}
    weeks = int(projection.get('projection_weeks') or facts.get('projection_weeks') or 4)
    cost = round(store_lsv * 7 * weeks, 2)
    cost_text = (
        f"If {day_word}'s rate of loss continued, store-controlled lost sales could cost "
        f"approximately £{cost:,.2f} over the next {weeks} weeks."
    )

    return {
        'issue': issue,
        'explanation': '\n'.join(explanation),
        'cost_if_not_fixed': cost_text,
        'recommended_action': drop_sentence,
    }


def _generate_markdown_compliance(signal: dict) -> dict:
    """Generate narrative for a MARKDOWN_COMPLIANCE alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    this_due = signal.get("this_week_markdowns_due", 0)
    this_completed = signal.get("this_week_completed_on_time", 0)
    this_rate = signal.get("this_week_compliance_rate", 0.0)
    last_rate = signal.get("last_week_compliance_rate")
    wow_change = signal.get("wow_change_pp")
    chain_rate = signal.get("chain_compliance_rate")
    below_chain = signal.get("below_chain_pp")
    projected_cost = signal.get("projected_cost") or 0.0

    facts = signal.get("facts", {})
    driver = facts.get("driver_assessment") or {}
    volume_classification = driver.get("volume_classification", "STABLE")
    volume_change_pct = driver.get("volume_change_pct")

    worst_depts = [
        row
        for row in facts.get("worst_departments_top3", [])
        if str(row.get("dept") or "").strip()
    ]

    parts = [site_name, "markdown on-time completion"]
    if "WOW" in triggers and wow_change is not None and wow_change < 0:
        parts.append(f"down {abs(wow_change):.1f}pp to {this_rate:.1f}%")
    if "VS_CHAIN" in triggers and below_chain is not None:
        parts.append(f"{below_chain:.1f}pp below chain average")
    issue = ": ".join([" ".join(parts[:-1]), parts[-1]]) if len(parts) > 2 else " ".join(parts)

    explanation_lines = [
        f"{this_completed} of {this_due} markdowns were completed on time this week ({this_rate:.1f}%).",
    ]
    if "WOW" in triggers and last_rate is not None and wow_change is not None:
        explanation_lines.append(
            f"Last week the on-time rate was {last_rate:.1f}% — down {abs(wow_change):.1f}pp."
        )
    if "VS_CHAIN" in triggers and chain_rate is not None:
        explanation_lines.append(
            f"Chain average is {chain_rate:.1f}% — this store is {below_chain:.1f}pp below."
        )
    if worst_depts:
        dept_list = ", ".join(
            f"{row['dept']} ({row['compliance_pct']:.1f}%)" for row in worst_depts[:3]
        )
        explanation_lines.append(f"Worst departments: {dept_list}.")
    if projected_cost:
        explanation_lines.append(
            f"At £{projected_cost:,.2f} per week, the four-week exposure is approximately "
            f"£{projected_cost * 4:,.2f} if not fixed."
        )

    dept_names = [row["dept"] for row in worst_depts[:3]]
    focus = ", ".join(dept_names) if dept_names else "the worst-performing departments"
    target = f"{last_rate:.1f}%" if last_rate is not None else "the prior week's rate"

    if volume_classification == "INCREASING" and volume_change_pct is not None:
        action = (
            f"Markdowns due are up {volume_change_pct:.0f}% while on-time completion has fallen "
            f"{abs(wow_change or 0):.0f}pp. Store manager to review staffing against markdown "
            f"workload this week, escalating to the area manager if hours cannot cover it. "
            f"Focus on {focus}. Review in 7 days against a target of {target}."
        )
    elif volume_classification == "DECREASING" and volume_change_pct is not None:
        action = (
            f"Markdown volume is down {abs(volume_change_pct):.0f}%, so the drop is not explained "
            f"by workload. Store manager to review the markdown routine with the team within 48 "
            f"hours, focusing on {focus}. Review in 7 days against a target of {target}."
        )
    else:
        action = (
            f"Markdown volume is broadly unchanged, so the drop is not explained by workload. "
            f"Store manager to review the markdown routine with the team within 48 hours, "
            f"focusing on {focus}. Review in 7 days against a target of {target}."
        )

    cost_if_not_fixed = f"£{projected_cost:,.2f} per week if not fixed."

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost_if_not_fixed,
        "recommended_action": action,
    }


def _generate_prompted_markdown_compliance(signal: dict) -> dict:
    """Generate narrative for a PROMPTED_MARKDOWN_COMPLIANCE alert."""
    site_name = signal.get("site_name") or f"Store {signal['store_id']}"
    triggers = signal.get("trigger_types", [])
    this_due = signal.get("this_week_prompts_issued", 0)
    this_completed = signal.get("this_week_prompts_actioned_on_time", 0)
    this_rate = signal.get("this_week_compliance_rate", 0.0)
    last_rate = signal.get("last_week_compliance_rate")
    wow_change = signal.get("wow_change_pp")
    chain_rate = signal.get("chain_compliance_rate")
    below_chain = signal.get("below_chain_pp")
    projected_cost = signal.get("projected_cost") or 0.0

    facts = signal.get("facts", {})
    driver = facts.get("driver_assessment") or {}
    volume_classification = driver.get("volume_classification", "STABLE")
    volume_change_pct = driver.get("volume_change_pct")

    worst_depts = [
        row
        for row in facts.get("worst_departments_top3", [])
        if str(row.get("dept") or "").strip()
    ]

    parts = [site_name, "prompted-markdown response"]
    if "WOW" in triggers and wow_change is not None and wow_change < 0:
        parts.append(f"down {abs(wow_change):.1f}pp to {this_rate:.1f}%")
    if "VS_CHAIN" in triggers and below_chain is not None:
        parts.append(f"{below_chain:.1f}pp below chain average")
    issue = ": ".join([" ".join(parts[:-1]), parts[-1]]) if len(parts) > 2 else " ".join(parts)

    explanation_lines = [
        f"{this_completed} of {this_due} prompts were actioned on time this week ({this_rate:.1f}%).",
    ]
    if "WOW" in triggers and last_rate is not None and wow_change is not None:
        explanation_lines.append(
            f"Last week the on-time rate was {last_rate:.1f}% — down {abs(wow_change):.1f}pp."
        )
    if "VS_CHAIN" in triggers and chain_rate is not None:
        explanation_lines.append(
            f"Chain average is {chain_rate:.1f}% — this store is {below_chain:.1f}pp below."
        )
    if worst_depts:
        dept_list = ", ".join(
            f"{row['dept']} ({row['compliance_pct']:.1f}%)" for row in worst_depts[:3]
        )
        explanation_lines.append(f"Worst departments: {dept_list}.")
    if projected_cost:
        explanation_lines.append(
            f"At £{projected_cost:,.2f} per week, the four-week exposure is approximately "
            f"£{projected_cost * 4:,.2f} if not fixed."
        )

    dept_names = [row["dept"] for row in worst_depts[:3]]
    focus = ", ".join(dept_names) if dept_names else "the worst-performing departments"
    target = f"{last_rate:.1f}%" if last_rate is not None else "the prior week's rate"

    if volume_classification == "INCREASING" and volume_change_pct is not None:
        action = (
            f"Prompt volume is up {volume_change_pct:.0f}% while on-time response has fallen "
            f"{abs(wow_change or 0):.0f}pp. Store manager to review staffing against prompt "
            f"volume this week, escalating to the area manager if hours cannot cover it. "
            f"Focus on {focus}. Review in 7 days against a target of {target}."
        )
    elif volume_classification == "DECREASING" and volume_change_pct is not None:
        action = (
            f"Prompt volume is down {abs(volume_change_pct):.0f}%, so the drop is not explained "
            f"by workload. Store manager to review the prompt response routine with the team within 48 "
            f"hours, focusing on {focus}. Review in 7 days against a target of {target}."
        )
    else:
        action = (
            f"Prompt volume is broadly unchanged, so the drop is not explained by workload. "
            f"Store manager to review the prompt response routine with the team within 48 hours, "
            f"focusing on {focus}. Review in 7 days against a target of {target}."
        )

    cost_if_not_fixed = f"£{projected_cost:,.2f} per week if not fixed."

    return {
        "issue": issue,
        "explanation": "\n".join(explanation_lines),
        "cost_if_not_fixed": cost_if_not_fixed,
        "recommended_action": action,
    }


def _generate_expiry_date_compliance(signal: dict) -> dict:
    facts = signal.get('facts') or {}
    driver = facts.get('driver_assessment') or {}
    departments = [row['dept'].title() for row in facts.get('worst_departments_top3', [])[:3]]
    focus = ', '.join(departments) if departments else 'the worst-performing departments'
    change = abs(signal.get('change_pp') or 0)
    prior_rate = signal.get('prev_7d_compliance_rate')
    target = f'{prior_rate:.2f}%' if prior_rate is not None else 'the prior period rate'
    volume_change = driver.get('volume_change_pct')
    if driver.get('likely_driver') == 'WORKLOAD':
        action = (
            f'Expiry check volume is up {volume_change:.0f}% while compliance has fallen {change:.0f}pp. '
            'Store manager to review staffing and rota coverage against task volume this week, escalating '
            f'to the area manager if hours cannot cover the volume. Focus on {focus}. Review in 7 days '
            f'against a target of {target}.'
        )
    else:
        prefix = 'Expiry check volume is broadly unchanged' if driver.get('volume_classification') == 'STABLE' else f'Expiry check volume is down {abs(volume_change or 0):.0f}%'
        action = (
            f'{prefix}, so the drop is not explained by workload. Store manager to review the expiry check '
            f'routine with the team within 48 hours, focusing on {focus}. Review in 7 days against a target of {target}.'
        )
    projected_cost = float(signal.get('projected_cost') or 0.0)
    return {
        'issue': f"{signal.get('site_name')} expiry date compliance fell {change:.1f}pp",
        'explanation': f"{signal.get('trailing_7d_checks_completed', 0)} of {signal.get('trailing_7d_checks_due', 0)} checks were completed.",
        'cost_if_not_fixed': f'£{projected_cost:,.2f} per week if not fixed.',
        'recommended_action': action,
    }


def _generate_big_drop_compliance(signal: dict, label: str, due_key: str, completed_key: str,
                                  completed_label: str, routine: str, volume_label: str) -> dict:
    site_name = signal.get('site_name') or f"Store {signal['store_id']}"
    due = signal.get(due_key, 0)
    completed = signal.get(completed_key, 0)
    rate = signal.get('this_day_compliance_rate', 0.0)
    previous_rate = signal.get('prev_day_compliance_rate')
    drop = signal.get('drop_pp') or 0.0
    chain_rate = signal.get('chain_compliance_rate')
    below_chain = signal.get('below_chain_pp')
    facts = signal.get('facts') or {}
    driver = facts.get('driver_assessment') or {}
    worst_depts = [
        row for row in facts.get('worst_departments_top3', [])
        if str(row.get('dept') or '').strip()
    ]

    explanation_lines = [
        f'{completed} of {due} {completed_label} today ({rate:.1f}%).',
    ]
    if previous_rate is not None:
        explanation_lines.append(
            f'The previous available day was {previous_rate:.1f}% — a drop of {drop:.1f}pp.'
        )
    if chain_rate is not None and below_chain is not None:
        explanation_lines.append(
            f'Chain average is {chain_rate:.1f}% — this store is {below_chain:.1f}pp below.'
        )
    if worst_depts:
        dept_list = ', '.join(
            f"{row['dept']} ({row['compliance_pct']:.1f}%)" for row in worst_depts[:3]
        )
        explanation_lines.append(f'Worst departments this week: {dept_list}.')

    focus = ', '.join(row['dept'] for row in worst_depts[:3]) or 'the worst-performing departments'
    target = f'{previous_rate:.1f}%' if previous_rate is not None else 'the previous-day rate'
    volume = driver.get('volume_classification', 'STABLE')
    volume_change = driver.get('volume_change_pct')
    if driver.get('likely_driver') == 'WORKLOAD' and volume_change is not None:
        action = (
            f'{volume_label} volume is up {volume_change:.0f}% while compliance dropped {drop:.0f}pp. '
            f'Store manager to review staffing and task coverage today, focusing on {focus}. '
            f'Review tomorrow against {target}.'
        )
    else:
        volume_context = (
            f'{volume_label} volume is down {abs(volume_change):.0f}%'
            if volume == 'DECREASING' and volume_change is not None
            else f'{volume_label} volume is broadly unchanged'
        )
        action = (
            f'{volume_context}, so workload does not explain the sudden drop. Store manager to review '
            f'the {routine} with the team today, focusing on {focus}. Review tomorrow against {target}.'
        )

    at_risk = float(signal.get('this_day_at_risk_value') or 0.0)
    cost = (
        f'£{at_risk:,.2f} is at risk from today’s missed activity.'
        if at_risk else f'The sudden fall in {label.lower()} increases immediate waste and availability risk.'
    )
    return {
        'issue': f'{site_name}: {label} dropped {drop:.1f}pp to {rate:.1f}%',
        'explanation': '\n'.join(explanation_lines),
        'cost_if_not_fixed': cost,
        'recommended_action': action,
    }


def _generate_big_drop_prompted_markdown_compliance(signal: dict) -> dict:
    return _generate_big_drop_compliance(
        signal, 'prompted-markdown compliance', 'this_day_prompts_issued',
        'this_day_prompts_actioned_on_time', 'prompts were actioned on time',
        'prompt response routine', 'Prompt',
    )


def _generate_big_drop_markdown_compliance(signal: dict) -> dict:
    return _generate_big_drop_compliance(
        signal, 'markdown compliance', 'this_day_markdowns_due',
        'this_day_completed_on_time', 'markdowns were completed on time',
        'markdown routine', 'Markdown',
    )


def _generate_big_drop_expiry_date_compliance(signal: dict) -> dict:
    return _generate_big_drop_compliance(
        signal, 'expiry-date compliance', 'this_day_checks_due',
        'this_day_checks_completed', 'expiry checks were completed',
        'expiry-check routine', 'Expiry check',
    )


def _generate_straight_to_bin(signal: dict) -> dict:
    """Generate narrative for a STRAIGHT_TO_BIN alert."""
    site_name = signal.get('site_name') or f"Store {signal['store_id']}"
    stb_value = signal.get('last_week_stb_value', 0.0)
    stb_items = signal.get('last_week_stb_items', 0)
    chain_avg = signal.get('chain_avg_stb_value_per_store', 0.0)
    multiple = signal.get('vs_chain_multiple', 0.0)
    threshold = signal.get('threshold_value', 100.0)
    projected_cost = signal.get('projected_cost', stb_value)

    facts = signal.get('facts', {})
    daily = facts.get('stb_by_day_last_week', [])
    worst_depts = [
        row for row in facts.get('worst_departments_by_value_top3', [])
        if str(row.get('dept') or '').strip().lower() not in {'', 'unknown', 'none', 'nan'}
    ]

    # Find peak days (top 2 by value)
    peak_days = sorted(daily, key=lambda x: x.get('value', 0), reverse=True)[:2]
    peak_day_names = [d['day'] for d in peak_days if d.get('value', 0) > 0]

    # Determine high vs near-threshold narrative
    is_high = multiple >= 2.5

    if is_high:
        issue = (
            f"{site_name}: \u00a3{stb_value:,.2f} of stock sent straight to bin last week "
            f"\u2014 {multiple:.1f}\u00d7 the chain average"
        )
    else:
        issue = (
            f"{site_name}: \u00a3{stb_value:,.2f} of stock sent straight to bin last week "
            f"\u2014 just above the \u00a3{threshold:,.0f} threshold"
        )

    explanation_lines = [
        f"{stb_items} items worth \u00a3{stb_value:,.2f} were sent straight to bin last week.",
        f"Chain average is \u00a3{chain_avg:,.2f} per store ({multiple:.1f}\u00d7).",
    ]
    if peak_day_names:
        explanation_lines.append(
            f"Peak days: {', '.join(peak_day_names)}."
        )
    if worst_depts:
        dept_list = ', '.join(
            f"{row['dept']} (\u00a3{row['value']:,.2f})" for row in worst_depts[:3]
        )
        explanation_lines.append(f"Worst departments: {dept_list}.")

    cost_if_not_fixed = f"\u00a3{projected_cost:,.2f} per week if not fixed."

    if is_high:
        dept_names = [row['dept'] for row in worst_depts[:3]]
        focus = ', '.join(dept_names) if dept_names else 'the worst-performing departments'
        peak_str = ' and '.join(peak_day_names) if peak_day_names else 'peak days'
        action = (
            f"Straight-to-bin value peaks on {peak_str}, when markdown compliance is at its lowest. "
            f"Store manager to review the markdown routine on those days this week, "
            f"focusing on {focus}. "
            f"Review in 7 days against the chain average of \u00a3{chain_avg:,.2f} per store."
        )
    else:
        action = (
            f"Value is just above the \u00a3{threshold:,.0f} threshold. "
            f"No action; monitor and review at next week's alert cycle. "
            f"Escalate if straight-to-bin value exceeds \u00a3{threshold:,.0f} again."
        )

    return {
        'issue': issue,
        'explanation': '\n'.join(explanation_lines),
        'cost_if_not_fixed': cost_if_not_fixed,
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
    triggers = signal.get("trigger_types", [])
    signal_type = signal.get("signal_type", "")

    if signal_type == "COMPLIANCE":
        return _generate_tick_and_flick(signal)

    if signal_type == "MARKDOWN_COMPLIANCE":
        return _generate_markdown_compliance(signal)

    if signal_type == "EXPIRY_DATE_COMPLIANCE":
        return _generate_expiry_date_compliance(signal)

    if signal_type == "PROMPTED_MARKDOWN_COMPLIANCE":
        return _generate_prompted_markdown_compliance(signal)

    if "TICK_AND_FLICK" in triggers:
        return _generate_tick_and_flick(signal)

    if signal_type == "OSA_STORE_ACTIONABLE":
        return _generate_osa_store_actionable(signal)

    if signal_type == "OSA_BIG_DROP":
        return _generate_osa_big_drop(signal)

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

    if signal_type == 'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE':
        return _generate_big_drop_prompted_markdown_compliance(signal)

    if signal_type == 'BIG_DROP_MARKDOWN_COMPLIANCE':
        return _generate_big_drop_markdown_compliance(signal)

    if signal_type == 'BIG_DROP_EXPIRY_DATE_COMPLIANCE':
        return _generate_big_drop_expiry_date_compliance(signal)

    if signal_type == 'STRAIGHT_TO_BIN':
        return _generate_straight_to_bin(signal)

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

    comp = facts.get("lsv_composition")
    if comp:
        explanation_lines += _fmt_lsv_composition_lines(comp)

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
        repeat_items = signal.get("repeat_item_details", [])
        if repeat_items:
            top_names = ", ".join(item["ppg"] for item in repeat_items[:2])
            action_parts.append(
                f"Investigate root cause for the worst repeat offenders \u2014 starting with "
                f"{top_names} \u2014 review replenishment parameters, supplier lead times, "
                f"and on-shelf capacity."
            )
        else:
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
