"""
Generic signal construction and merging
========================================
Replaces the per-type ``make_<type>_signal`` factories and the hard-coded
field list in the old ``_merge_signals``.

``make_signal``
    Builds a signal dict with the standard envelope (signal_type, merge_key,
    store_id, site_name, trigger_types) plus arbitrary metric fields.

``merge_signals``
    Collapses signals sharing a ``merge_key``: trigger_types are unioned,
    any non-None field from a later signal wins, and ``this_week_lsv``
    takes the maximum (preserving the OSA merge semantics).
"""

from __future__ import annotations

# Fields merged with "max" semantics rather than "later non-None wins"
_MAX_FIELDS = ('this_week_lsv',)

# Envelope fields that are never overwritten during a merge
_ENVELOPE = ('signal_type', 'merge_key', 'store_id', 'trigger_types')


def make_signal(
    signal_type: str,
    store_id: int,
    trigger: str,
    site_name: str | None = None,
    key_extra: tuple = (),
    **fields,
) -> dict:
    """
    Build a signal dict.

    Parameters
    ----------
    signal_type : e.g. 'WASTE'
    store_id    : int
    trigger     : single trigger name, e.g. 'WOW'
    site_name   : human-readable store name; defaults to 'Store <id>'
    key_extra   : extra merge-key components beyond (signal_type, store_id),
                  e.g. (department,) for OSA or (item_id,) for MARKDOWN_SKU
    **fields    : metric fields stamped straight onto the signal
    """
    return {
        'signal_type':   signal_type,
        'merge_key':     (signal_type, store_id, *key_extra),
        'store_id':      store_id,
        'site_name':     site_name or f'Store {store_id}',
        'trigger_types': [trigger],
        **fields,
    }


def merge_signals(all_signals: list[dict]) -> list[dict]:
    """
    Collapse a flat list of signals into one signal per ``merge_key``.

    Generic rules (no per-type field lists to maintain):
    - ``trigger_types`` lists are unioned, order preserved
    - any non-None field from a later signal overwrites the earlier value
    - fields in ``_MAX_FIELDS`` take the maximum across signals
    """
    groups: dict = {}
    for sig in all_signals:
        key = sig['merge_key']
        if key not in groups:
            groups[key] = {**sig}
            continue

        existing = groups[key]
        existing['trigger_types'] = list(
            dict.fromkeys(existing['trigger_types'] + sig['trigger_types'])
        )
        for fname, value in sig.items():
            if fname in _ENVELOPE or value is None:
                continue
            if fname in _MAX_FIELDS:
                current = existing.get(fname)
                if current is None or value > current:
                    existing[fname] = value
            else:
                existing[fname] = value
    return list(groups.values())
