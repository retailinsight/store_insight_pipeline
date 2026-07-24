# Triage Label Configuration

## Label Mapping

The following canonical triage roles map directly to GitHub labels:

| Canonical Role | GitHub Label | Description |
|----------------|--------------|-------------|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate the issue |
| `needs-info` | `needs-info` | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, AFK-ready for agent implementation |
| `ready-for-human` | `ready-for-human` | Ready for human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

## Usage
Skills that perform triage operations will apply these exact labels to GitHub issues. No label mapping is required since the canonical names match the GitHub label names.
