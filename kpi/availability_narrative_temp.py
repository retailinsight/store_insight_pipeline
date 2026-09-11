"""
Deterministic availability summary narrative generator.

Implements the lightweight pilot specification for the weekly availability
summary: three fixed-sentence manager-facing bullets built from pre-ranked,
validated facts rather than from open-ended model generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OsaSnapshot:
    """Current and previous OSA values for a store or cluster."""

    current_pct: float | None
    previous_pct: float | None


@dataclass
class DepartmentCandidate:
    """A department's current/previous OSA and commercial data for ranking."""

    department: str
    current_osa_pct: float
    previous_osa_pct: float
    lost_sales_value: float
    quality_valid: bool = True


@dataclass
class NarrativeConfig:
    """Tunable thresholds for candidate eligibility and anomaly quarantine."""

    min_positive_rows: int = 10
    max_unknown_row_pct: float = 10.0
    max_abs_movement_pp: float = 50.0
    min_positive_improvement_pp: float = 0.0
    min_negative_deterioration_pp: float = 0.0


def _safe_pct(value: Any) -> float | None:
    """Coerce a raw value to a percentage or None if missing."""
    if value is None:
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if pct != pct:  # NaN
        return None
    return pct


def _is_valid(candidate: DepartmentCandidate, cfg: NarrativeConfig) -> bool:
    """Return True if a department can be considered for a callout."""
    if not candidate.quality_valid:
        return False
    if candidate.current_osa_pct is None or candidate.previous_osa_pct is None:
        return False
    movement = abs(candidate.current_osa_pct - candidate.previous_osa_pct)
    if movement > cfg.max_abs_movement_pp:
        return False
    return True


def _choose_direction_verb(current: float, previous: float) -> str:
    """Pick the verb for an OSA movement."""
    return "rose" if current >= previous else "fell"


def rank_positive_candidate(
    candidates: list[DepartmentCandidate], cfg: NarrativeConfig
) -> DepartmentCandidate | None:
    """
    Return the most commercially meaningful positive department.

    Eligible candidates improved week-on-week. They are ranked by the largest
    absolute percentage-point improvement.
    """
    eligible = [
        c
        for c in candidates
        if _is_valid(c, cfg)
        and c.current_osa_pct > c.previous_osa_pct
        and (c.current_osa_pct - c.previous_osa_pct) > cfg.min_positive_improvement_pp
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda c: c.current_osa_pct - c.previous_osa_pct)


def rank_negative_candidates(
    candidates: list[DepartmentCandidate], cfg: NarrativeConfig, max_count: int = 2
) -> list[DepartmentCandidate]:
    """
    Return up to ``max_count`` negative department callouts.

    Eligible candidates deteriorated week-on-week. Primary sort is by current
    lost-sales value (commercial exposure), tie-broken by the largest absolute
    percentage-point drop.
    """
    eligible = [
        c
        for c in candidates
        if _is_valid(c, cfg)
        and c.previous_osa_pct > c.current_osa_pct
        and (c.previous_osa_pct - c.current_osa_pct) > cfg.min_negative_deterioration_pp
    ]
    if not eligible:
        return []
    eligible.sort(key=lambda c: (c.lost_sales_value, c.previous_osa_pct - c.current_osa_pct), reverse=True)
    return eligible[:max_count]


def render_summary(
    store_controllable: OsaSnapshot,
    overall: OsaSnapshot,
    cluster_pct: float | None,
) -> str:
    """Render sentence 1: the whole-store availability summary."""
    sc_current = store_controllable.current_pct
    sc_previous = store_controllable.previous_pct
    ov_current = overall.current_pct
    ov_previous = overall.previous_pct

    if sc_current is None or sc_previous is None or ov_current is None or ov_previous is None:
        raise ValueError("Summary requires current and previous store-controllable and overall OSA")

    sc_verb = _choose_direction_verb(sc_current, sc_previous)
    ov_verb = _choose_direction_verb(ov_current, ov_previous)
    cluster_text = f"{cluster_pct:.1f}%" if cluster_pct is not None else "not available"

    return (
        f"Store-controllable availability {sc_verb} from {sc_previous:.1f}% last week "
        f"to {sc_current:.1f}% this week, while overall availability {ov_verb} "
        f"from {ov_previous:.1f}% to {ov_current:.1f}%, compared with a society average "
        f"of {cluster_text}."
    )


def render_positive(candidate: DepartmentCandidate | None) -> str:
    """Render sentence 2: the single most meaningful department improvement."""
    if candidate is None:
        return "No material department improvement stood out in the completed data this week."
    return (
        f"{candidate.department} improved from {candidate.previous_osa_pct:.1f}% "
        f"to {candidate.current_osa_pct:.1f}%."
    )


def render_negative(candidates: list[DepartmentCandidate]) -> str:
    """Render sentence 3: one or two negative department callouts."""
    if not candidates:
        return "No material department deterioration stood out in the completed data this week."

    parts: list[str] = []
    for c in candidates:
        segment = (
            f"{c.department} fell from {c.previous_osa_pct:.1f}% to {c.current_osa_pct:.1f}%"
        )
        if c.lost_sales_value:
            segment += f" with £{round(c.lost_sales_value)} in lost sales"
        parts.append(segment)

    if len(parts) == 1:
        return parts[0] + "."
    return parts[0] + ", while " + parts[1] + "."


def build_narrative(
    store_controllable: OsaSnapshot,
    overall: OsaSnapshot,
    cluster_pct: float | None,
    departments: list[DepartmentCandidate],
    cfg: NarrativeConfig | None = None,
) -> list[str]:
    """
    Build the three fixed-order availability sentences deterministically.

    Parameters
    ----------
    store_controllable : OsaSnapshot
        Current and previous Store Controllable OSA percentages.
    overall : OsaSnapshot
        Current and previous overall availability percentages.
    cluster_pct : float | None
        Current cluster-average overall OSA percentage.
    departments : list[DepartmentCandidate]
        One candidate per department, used for positive and negative ranking.
    cfg : NarrativeConfig | None
        Thresholds for eligibility and anomaly quarantine.

    Returns
    -------
    list[str]
        Exactly three strings: summary, positive, negative.
    """
    if cfg is None:
        cfg = NarrativeConfig()

    positive = rank_positive_candidate(departments, cfg)
    negatives = rank_negative_candidates(departments, cfg)

    return [
        render_summary(store_controllable, overall, cluster_pct),
        render_positive(positive),
        render_negative(negatives),
    ]
