"""
stages_testing — Vertically-Sliced Pipeline Prototype
======================================================
An experimental re-organisation of ``pipeline/stages`` where each signal type
owns one folder containing everything about it (detection metric, scoring,
fact gatherers, investigation config), instead of being spread across four
horizontal stage folders.

See README.md in this folder for the full design.

Public API (same contracts as the existing stages)
--------------------------------------------------
    from store_insight.pipeline.stages_testing import runner
    runner.detect_signals(...)   -> list[signal_dict]
    runner.score_all(...)        -> None (stamps signal['score'] in-place)
    runner.enrich_signals(...)   -> list[signal_dict with 'facts']
    runner.investigate(...)      -> dict of narrative fields
"""
