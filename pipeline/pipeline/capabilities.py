"""
Capability Validation
=====================

Catches the configuration mistake of "client X has detector Y enabled but
hasn't deployed the adapter view Y needs" *before* the pipeline runs and
fails 30 seconds in with a confusing ``Table 'XYZ' does not exist``.

Design
------
- Detectors and gatherers declare what data they need via their ``detect``
  / ``gather`` function signatures.  The Stage 1 / Stage 2 dispatchers
  already use ``inspect.signature`` to filter context kwargs to only those
  the function declares (see ``stages/_1_detect/detect.py:detect_signals``
  and ``stages/_3_facts/facts.py:enrich_signals``).  We piggyback on that
  source of truth — no new declarations needed in detector files.

- A small explicit mapping ``PARAM_TO_CONTRACTS`` translates kwarg names
  ("osa", "feedback", "markdown_log" …) to the canonical contract names
  declared in ``pipeline/contracts/<name>_v1.yaml``.

- A client's *capabilities* (the set of contracts they have an adapter
  view for) is discovered from ``pipeline/adapters/<client>/*.sql``
  filenames, OR from an explicit ``cfg['capabilities']`` list when one
  is provided (useful for testing).

- ``validate(cfg)`` returns a list of human-readable issue strings.
  An empty list means the config is consistent.  The CLI in
  ``run_batch.py`` aborts on any issues unless
  ``--skip-capability-check`` is passed.

Adding a new context kwarg
--------------------------
When ``detect_signals`` or ``enrich_signals`` grows a new kwarg that
carries a Snowpark DataFrame backed by a contract, add an entry to
``PARAM_TO_CONTRACTS`` here.  Tests in ``test_capabilities.py`` will
reject the new kwarg until the mapping is updated, so this can't drift
silently.
"""

from __future__ import annotations

import inspect
from pathlib import Path

# ---------------------------------------------------------------------------
# kwarg → contract mapping
# ---------------------------------------------------------------------------

# Each kwarg accepted by a detect()/gather() function that carries a
# Snowpark DataFrame has an entry here.  Multiple contracts per kwarg
# are allowed (the OSA loader joins hierarchy in, so any detector that
# accepts ``osa`` transitively requires both contracts).
PARAM_TO_CONTRACTS: dict[str, list[str]] = {
    'osa':             ['osa', 'hierarchy'],
    'feedback':        ['feedback'],
    'markdown_log':    ['markdown_log'],
    'markdown_sales':  ['markdown_sales'],
    'wastage':         ['wastage'],
    'item_hierarchy':  ['wmd_hierarchy'],
    'store_hierarchy': ['store_hierarchy'],
}


# ---------------------------------------------------------------------------
# Signature inspection
# ---------------------------------------------------------------------------

def required_contracts(fn) -> set[str]:
    """
    Return the set of contract names that ``fn`` (a ``detect`` or ``gather``
    function) requires, inferred from its parameter list via
    ``PARAM_TO_CONTRACTS``.

    Parameters not listed in the mapping (window dates, thresholds, ``cfg``,
    ``signals`` etc.) are ignored.
    """
    params = inspect.signature(fn).parameters
    needed: set[str] = set()
    for param_name in params:
        for contract in PARAM_TO_CONTRACTS.get(param_name, []):
            needed.add(contract)
    return needed


# ---------------------------------------------------------------------------
# Adapter-file discovery
# ---------------------------------------------------------------------------

_THIS_FILE    = Path(__file__).resolve()
_PIPELINE_DIR = _THIS_FILE.parent.parent
_ADAPTERS_DIR = _PIPELINE_DIR / 'adapters'


def discover_capabilities(client: str) -> set[str]:
    """
    Return the set of contracts a client has an adapter SQL file for,
    derived from filenames under ``pipeline/adapters/<client>/``.

    A missing ``<client>`` directory yields an empty set — the validator
    will then surface every required contract as missing, which is the
    correct behaviour for a brand-new client who hasn't shipped any
    adapters yet.
    """
    adapter_dir = _ADAPTERS_DIR / client
    if not adapter_dir.is_dir():
        return set()
    return {p.stem for p in adapter_dir.glob('*.sql')}


# ---------------------------------------------------------------------------
# Detector / gatherer iteration
# ---------------------------------------------------------------------------

def _detector_module_name(mod) -> str:
    """
    ``store_insight.pipeline.stages._1_detect.detectors.osa.wow``
    →
    ``'osa.wow'``

    Mirrors the same convention used by ``detect_signals`` so the names in
    error messages match what the user types into ``cfg.detectors.enabled``.
    """
    parts = mod.__name__.split('.')
    try:
        idx = parts.index('detectors')
        return '.'.join(parts[idx + 1:])
    except ValueError:
        return parts[-1]


def _gatherer_module_name(mod) -> str:
    """
    ``store_insight.pipeline.stages._3_facts.gatherers.osa_chain_drift``
    →
    ``'osa_chain_drift'``
    """
    return mod.__name__.split('.')[-1]


# ---------------------------------------------------------------------------
# Public validate()
# ---------------------------------------------------------------------------

def validate(cfg: dict) -> list[str]:
    """
    Return a list of human-readable issue strings for every enabled
    detector / gatherer whose required contracts aren't deployed for
    this client.  Empty list ⇒ config is consistent.

    The function does not raise — it returns the list so callers (CLI,
    handler, tests) can decide how to surface issues.

    Capabilities resolution
    -----------------------
    - If ``cfg['capabilities']`` is explicitly set (list of contract names),
      that's the authoritative set.  Useful for tests and for clients
      whose adapters live outside the standard layout.
    - Otherwise we auto-discover from ``pipeline/adapters/<client>/*.sql``.

    Detector/gatherer filtering
    ---------------------------
    - ``cfg['detectors']['enabled']`` (if set) restricts which detectors
      we validate; detectors not in that list are *not* a capability
      requirement.
    - ``cfg['gatherers'][<signal_type>]`` (if set) does the same for
      gatherers within that signal type.  Signal types whose detectors
      are all disabled are also skipped (a gatherer with no firing
      signals is dead code).
    """
    # Lazy imports — keep this module decoupled from the registry so it
    # can be unit-tested without spinning up the full pipeline import graph.
    from store_insight.pipeline.stages._1_detect import registry as det_reg
    from store_insight.pipeline.stages._3_facts import registry as gth_reg

    issues: list[str] = []

    # Support both dict and Pydantic model inputs
    if isinstance(cfg, dict):
        client = cfg.get('client_name', 'default')
        capabilities_attr = cfg.get('capabilities')
        detectors_cfg = cfg.get('detectors')
        gatherers_cfg = cfg.get('gatherers', {})
    else:
        # Pydantic model - use getattr
        client = getattr(cfg, 'client_name', 'default')
        capabilities_attr = getattr(cfg, 'capabilities', None)
        detectors_cfg = getattr(cfg, 'detectors', None)
        gatherers_cfg = getattr(cfg, 'gatherers', {})

    # ── Resolve capabilities ────────────────────────────────
    if capabilities_attr is not None:
        capabilities = set(capabilities_attr)
    else:
        capabilities = discover_capabilities(client)

    # ── Which detectors are enabled? ────────────────────────
    enabled_detectors: set[str] | None = None
    if detectors_cfg is not None:
        if isinstance(detectors_cfg, dict):
            enabled_list = detectors_cfg.get('enabled')
        else:
            # Pydantic model
            enabled_list = getattr(detectors_cfg, 'enabled', None)
        if enabled_list is not None:
            enabled_detectors = set(enabled_list)

    # Track which signal types still have any enabled detector — gatherers
    # for fully-disabled signal types are dead code and don't need
    # validation.
    enabled_signal_types: set[str] = set()

    # ── Validate detectors ──────────────────────────────────
    for mod in det_reg.ALL_DETECTORS:
        name = _detector_module_name(mod)
        if enabled_detectors is not None and name not in enabled_detectors:
            continue

        needed  = required_contracts(mod.detect)
        missing = needed - capabilities
        if missing:
            issues.append(
                f"detector '{name}' requires contracts {sorted(missing)} but "
                f"client '{client}' has no adapter for them. Either deploy "
                f"`pipeline/adapters/{client}/<contract>.sql` (and the view "
                f"to Snowflake via `python pipeline/tools/deploy_views.py "
                f"--client {client}`), or remove '{name}' from "
                f"cfg.detectors.enabled."
            )

        # METADATA on the detector tells us what signal type it produces;
        # use it to track which gatherers we still need to validate.
        meta = getattr(mod, 'METADATA', None)
        if meta is not None:
            # METADATA.name is the signal-type label (e.g. 'TICK_AND_FLICK',
            # 'WOW') but signal_type buckets are coarser (e.g. 'COMPLIANCE',
            # 'OSA').  Easier to derive signal_type from the alert_type
            # subfolder.
            parts = mod.__name__.split('.')
            try:
                idx = parts.index('detectors')
                alert_folder = parts[idx + 1]
                enabled_signal_types.add(alert_folder.upper())
            except ValueError:
                pass

    # ── Validate gatherers ──────────────────────────────────
    cfg_gatherers = gatherers_cfg

    for signal_type, gatherers in gth_reg.SIGNAL_TYPE_GATHERERS.items():
        # If detector filtering is active and *no* detector for this signal
        # type is enabled, skip — its gatherers can't fire anyway.
        if enabled_detectors is not None and signal_type not in enabled_signal_types:
            continue

        # Per-signal-type gatherer filter.
        if cfg_gatherers is not None:
            if isinstance(cfg_gatherers, dict):
                signal_gatherers = cfg_gatherers.get(signal_type)
            else:
                # Pydantic model
                signal_gatherers = getattr(cfg_gatherers, signal_type, None)
            if signal_gatherers is not None:
                allowed   = set(signal_gatherers)
                gatherers = [g for g in gatherers if _gatherer_module_name(g) in allowed]

        for mod in gatherers:
            gname  = _gatherer_module_name(mod)
            needed = required_contracts(mod.gather)
            missing = needed - capabilities
            if missing:
                issues.append(
                    f"gatherer '{gname}' (signal_type={signal_type}) requires "
                    f"contracts {sorted(missing)} but client '{client}' has no "
                    f"adapter for them. Either deploy the adapter view, or "
                    f"remove '{gname}' from cfg.gatherers.{signal_type}."
                )

    return issues
