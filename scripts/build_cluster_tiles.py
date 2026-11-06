"""Fold a notes pull + agent classification into tile-shaped JSON.

Mechanical merge only — the cause labels come from the classification file
written by the agent, not from this script.

Usage:
    python scripts/build_cluster_tiles.py <pull.json> <classification.json>
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

CAUSE_LABELS = {
    "late_deliveries": "Late or delayed deliveries",
    "equipment_faults": "Fridge, freezer or chiller faults",
    "supplier_shortages": "Supplier or depot shortages",
    "short_staffed": "Busy or short-staffed",
    "theft": "Theft",
}
MIN_STORES = 2  # tiles only render when >= MIN_STORES stores share the cause


def main():
    pull = json.loads(Path(sys.argv[1]).read_text())
    classification = json.loads(Path(sys.argv[2]).read_text())
    labels = classification["labels"]
    default = classification.get("default_label", "other")

    by_cause = defaultdict(list)
    counts = defaultdict(int)
    for a in pull["actions"]:
        cause = labels.get(a["action_id"], default)
        counts[cause] += 1
        if cause in CAUSE_LABELS:
            by_cause[cause].append(a)

    tiles = []
    for cause_key, actions in by_cause.items():
        stores = defaultdict(list)
        for a in actions:
            text_parts = [a.get("outcome_reason") or ""]
            text_parts += [n["message"] for n in a.get("notes", [])]
            stores[(a["store_id"], a["store_name"])].append(
                {
                    "action_id": a["action_id"],
                    "alert_type": a["alert_type"],
                    "section": a["section"],
                    "outcome": a["outcome"],
                    "completed_at": a["updated_at"],
                    "by": a["assignee_initials"],
                    "text": " ".join(t for t in text_parts if t).strip(),
                }
            )
        if len(stores) < MIN_STORES:
            continue
        tiles.append(
            {
                "cause_key": cause_key,
                "label": CAUSE_LABELS[cause_key],
                "stores_affected": len(stores),
                "action_count": sum(len(v) for v in stores.values()),
                "stores": [
                    {
                        "store_id": sid,
                        "store_name": sname,
                        "actions": acts,
                    }
                    for (sid, sname), acts in sorted(
                        stores.items(), key=lambda kv: -len(kv[1])
                    )
                ],
            }
        )
    tiles.sort(key=lambda t: -t["stores_affected"])

    out = {
        "window": {
            "days": pull["window_days"],
            "pulled_at": pull["pulled_at"],
        },
        "group": "smart_action_responses",
        "tiles": tiles,
        "unclassified": {
            "other": counts["other"],
            "noise": counts["noise"],
        },
        "below_threshold": [
            {
                "cause_key": k,
                "label": CAUSE_LABELS[k],
                "stores_affected": len({a["store_id"] for a in v}),
                "action_count": len(v),
            }
            for k, v in by_cause.items()
            if len({a["store_id"] for a in v}) < MIN_STORES
        ],
    }
    out_path = Path(sys.argv[1]).with_name(
        Path(sys.argv[1]).stem.replace("cluster_notes", "cluster_tiles") + ".json"
    )
    out_path.write_text(json.dumps(out, indent=2))
    print(f"written: {out_path}")
    for t in tiles:
        print(f"  {t['label']}: {t['stores_affected']} stores, {t['action_count']} actions")
    for b in out["below_threshold"]:
        print(f"  (below threshold) {b['label']}: {b['stores_affected']} stores")


if __name__ == "__main__":
    main()
