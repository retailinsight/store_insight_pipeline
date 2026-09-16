"""Pure workflow suppression rules applied before the per-store card cap."""


def suppress_signals(signals: list[dict], active_issue_keys: set[str],
                     resolved_issue_keys: set[str]) -> tuple[list[dict], list[dict]]:
    kept = []
    log = []
    for signal in signals:
        issue_key = signal['issue_key']
        if issue_key in active_issue_keys:
            log.append({'issue_key': issue_key, 'status': 'IN_PROGRESS'})
        elif issue_key in resolved_issue_keys:
            log.append({'issue_key': issue_key, 'status': 'SUPPRESSED'})
        else:
            kept.append(signal)
    return kept, log
