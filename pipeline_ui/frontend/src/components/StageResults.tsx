import { useMemo, useState } from "react";
import { RunResult } from "../lib/api";

type Tab = "summary" | "cards" | "signals" | "runconfig";

const gbp = (n: number) =>
  `£${(Number(n) || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function StageResults({ result, runConfig }: { result: RunResult; runConfig?: Record<string, any> | null }) {
  const [tab, setTab]           = useState<Tab>("summary");
  const [storeFilter, setStore] = useState<string>("all");
  const [typeFilter, setType]   = useState<string>("all");
  const [sortBy, setSortBy]     = useState<"score" | "cost">("score");

  // Derive unique stores and signal types from all signals (pre-filter data)
  const allSignals = result.signals ?? [];
  const stores = useMemo(() => {
    const seen = new Map<number, string>();
    for (const s of allSignals) {
      if (!seen.has(s.store_id)) seen.set(s.store_id, s.store_name ?? `Store ${s.store_id}`);
    }
    return Array.from(seen.entries()).sort((a, b) => (a[1] > b[1] ? 1 : -1));
  }, [allSignals]);

  const signalTypes = useMemo(() => {
    const seen = new Set<string>();
    for (const s of allSignals) if (s.signal_type) seen.add(s.signal_type);
    return Array.from(seen).sort();
  }, [allSignals]);

  // Filtered + sorted cards
  const cards = useMemo(() => {
    const filtered = (result.cards ?? []).filter(c => {
      if (storeFilter !== "all" && String(c.store_id) !== storeFilter) return false;
      if (typeFilter  !== "all" && c.signal_type !== typeFilter)       return false;
      return true;
    });
    const val = (c: any) =>
      sortBy === "cost"
        ? Number(c.projected_cost) || 0
        : Number(c.score ?? c.sort_value) || 0;
    return [...filtered].sort((a, b) => val(b) - val(a));
  }, [result.cards, storeFilter, typeFilter, sortBy]);

  // Total projected cost across filtered cards
  const totalCost = useMemo(
    () => cards.reduce((sum, c) => sum + (Number(c.projected_cost) || 0), 0),
    [cards],
  );

  // ── Summary: breakdown of which signals triggered (count + cost) ──────────
  const summary = useMemo(() => {
    const byType = new Map<string, { count: number; cost: number }>();
    const byTrigger = new Map<string, { signalType: string; trigger: string; count: number; cost: number }>();
    let totalCount = 0;
    let totalCost = 0;

    for (const s of allSignals) {
      const cost = Number(s.projected_cost) || 0;
      totalCount += 1;
      totalCost += cost;

      const type = s.signal_type || "unknown";
      const t = byType.get(type) ?? { count: 0, cost: 0 };
      t.count += 1;
      t.cost += cost;
      byType.set(type, t);

      const triggers = Array.isArray(s.trigger_types) && s.trigger_types.length
        ? s.trigger_types
        : ["(none)"];
      for (const tr of triggers) {
        const key = `${type}\u0000${tr}`;
        const g = byTrigger.get(key) ?? { signalType: type, trigger: tr, count: 0, cost: 0 };
        g.count += 1;
        g.cost += cost;
        byTrigger.set(key, g);
      }
    }

    const byTypeRows = Array.from(byType.entries())
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.cost - a.cost);

    const byTriggerRows = Array.from(byTrigger.values())
      .sort((a, b) =>
        a.signalType === b.signalType ? b.cost - a.cost : (a.signalType > b.signalType ? 1 : -1),
      );

    return {
      byType: byTypeRows,
      byTrigger: byTriggerRows,
      totalCount,
      totalCost,
    };
  }, [allSignals]);

  return (
    <div className="p-4 space-y-3">
      {/* Tab bar */}
      <div className="flex gap-1 border-b text-sm">
        <TabBtn label="Summary" active={tab === "summary"} onClick={() => setTab("summary")} />
        <TabBtn label={`Cards (${result.counts.cards})`} active={tab === "cards"}   onClick={() => setTab("cards")} />
        <TabBtn label={`Signals (${result.counts.signals})`} active={tab === "signals"} onClick={() => setTab("signals")} />
        {runConfig && <TabBtn label="Run config" active={tab === "runconfig"} onClick={() => setTab("runconfig")} />}
      </div>

      {/* Summary tab */}
      {tab === "summary" && (
        <SummaryView summary={summary} />
      )}

      {/* Cards tab */}
      {tab === "cards" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-2 items-center">
            <select
              value={storeFilter}
              onChange={e => setStore(e.target.value)}
              className="text-xs px-2 py-1 border rounded bg-white"
            >
              <option value="all">All stores</option>
              {stores.map(([id, name]) => (
                <option key={id} value={String(id)}>{name}</option>
              ))}
            </select>
            <select
              value={typeFilter}
              onChange={e => setType(e.target.value)}
              className="text-xs px-2 py-1 border rounded bg-white"
            >
              <option value="all">All types</option>
              {signalTypes.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <div className="inline-flex items-center gap-1">
              <span className="text-xs text-muted">Rank by</span>
              <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5">
                {(["score", "cost"] as const).map(k => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setSortBy(k)}
                    className={`px-2 py-0.5 rounded text-xs font-medium transition ${
                      sortBy === k ? "bg-violet-600 text-white" : "text-slate-600 hover:text-ink"
                    }`}
                  >
                    {k === "score" ? "Score" : "Cost"}
                  </button>
                ))}
              </div>
            </div>
            <div className="ml-auto text-xs text-muted">
              {cards.length} card{cards.length !== 1 ? "s" : ""} · est. cost{" "}
              <span className="font-semibold text-ink">£{totalCost.toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
            </div>
          </div>

          {/* Card list */}
          {cards.length === 0 ? (
            <div className="text-muted text-sm">No cards match the current filters.</div>
          ) : (
            <div className="space-y-3 max-h-[65vh] overflow-auto pr-1">
              {cards.map((c, i) => <AlertCard key={i} card={c} />)}
            </div>
          )}
        </>
      )}

      {/* Run config tab — exact payload sent to the run */}
      {tab === "runconfig" && runConfig && (
        <RunConfigView runConfig={runConfig} />
      )}

      {/* Raw signals tab */}
      {tab === "signals" && (
        <div className="space-y-2 max-h-[65vh] overflow-auto">
          {(result.signals ?? []).length === 0 && <div className="text-muted text-sm">No signals.</div>}
          {(result.signals ?? []).map((s, i) => (
            <details key={i} className="border rounded">
              <summary className="px-3 py-2 text-xs cursor-pointer bg-slate-50 flex items-center justify-between">
                <span>{s.signal_type} · store {s.store_id} · {s.department ?? "—"}</span>
                <span className="text-muted">{Array.isArray(s.trigger_types) ? s.trigger_types.join(", ") : ""} · £{Number(s.projected_cost ?? 0).toFixed(0)}</span>
              </summary>
              <pre className="p-3 text-xs overflow-auto">{JSON.stringify(s, null, 2)}</pre>
            </details>
          ))}
        </div>
      )}

    </div>
  );
}

type SummaryRow = { name: string; count: number; cost: number };
type TriggerRow = { signalType: string; trigger: string; count: number; cost: number };
type Summary = {
  byType: SummaryRow[];
  byTrigger: TriggerRow[];
  totalCount: number;
  totalCost: number;
};

function SummaryView({ summary }: { summary: Summary }) {
  if (summary.totalCount === 0) {
    return <div className="text-muted text-sm">No signals triggered.</div>;
  }
  return (
    <div className="space-y-4 max-h-[65vh] overflow-auto pr-1">
      {/* Headline totals */}
      <div className="grid grid-cols-2 gap-2">
        <div className="border rounded-lg bg-white px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-muted">Signals triggered</div>
          <div className="text-xl font-semibold text-ink">{summary.totalCount}</div>
        </div>
        <div className="border rounded-lg bg-white px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-muted">Total est. cost</div>
          <div className="text-xl font-semibold text-red-700">{gbp(summary.totalCost)}</div>
        </div>
      </div>

      <SummaryTable title="By signal type" rows={summary.byType} total={summary.totalCount} />
      <TriggerTable title="By trigger" rows={summary.byTrigger} total={summary.totalCount} />
    </div>
  );
}

function TriggerTable({ title, rows, total }: { title: string; rows: TriggerRow[]; total: number }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ink mb-1">{title}</div>
      <table className="w-full text-xs border rounded-lg overflow-hidden bg-white">
        <thead>
          <tr className="bg-slate-50 text-muted text-left">
            <th className="px-2 py-1.5 font-medium">Signal type</th>
            <th className="px-2 py-1.5 font-medium">Trigger</th>
            <th className="px-2 py-1.5 font-medium text-right">Count</th>
            <th className="px-2 py-1.5 font-medium text-right">Share</th>
            <th className="px-2 py-1.5 font-medium text-right">Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const firstOfType = i === 0 || rows[i - 1].signalType !== r.signalType;
            return (
              <tr key={`${r.signalType}\u0000${r.trigger}`} className={`border-t ${firstOfType ? "border-slate-300" : ""}`}>
                <td className="px-2 py-1.5 text-muted">{firstOfType ? r.signalType : ""}</td>
                <td className="px-2 py-1.5 text-ink">{r.trigger}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{r.count}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-muted">
                  {total ? `${Math.round((r.count / total) * 100)}%` : "—"}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums font-medium text-red-700">{gbp(r.cost)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SummaryTable({ title, rows, total }: { title: string; rows: SummaryRow[]; total: number }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ink mb-1">{title}</div>
      <table className="w-full text-xs border rounded-lg overflow-hidden bg-white">
        <thead>
          <tr className="bg-slate-50 text-muted text-left">
            <th className="px-2 py-1.5 font-medium">Name</th>
            <th className="px-2 py-1.5 font-medium text-right">Count</th>
            <th className="px-2 py-1.5 font-medium text-right">Share</th>
            <th className="px-2 py-1.5 font-medium text-right">Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.name} className="border-t">
              <td className="px-2 py-1.5 text-ink">{r.name}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.count}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-muted">
                {total ? `${Math.round((r.count / total) * 100)}%` : "—"}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums font-medium text-red-700">{gbp(r.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunConfigView({ runConfig }: { runConfig: Record<string, any> }) {
  const [copied, setCopied] = useState(false);
  const json = useMemo(() => JSON.stringify(runConfig, null, 2), [runConfig]);

  const filename = useMemo(() => {
    const client = runConfig.client ?? "experiment";
    const date   = runConfig.analysis_date ?? "run";
    const stamp  = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    return `experiment-${client}-${date}-${stamp}.json`;
  }, [runConfig]);

  const download = () => {
    const blob = new Blob([json], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  const skillCount = runConfig.skills ? Object.keys(runConfig.skills).length : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={download}
          className="px-2.5 py-1 rounded text-xs font-medium bg-violet-600 text-white hover:bg-violet-700 transition"
        >
          Download JSON
        </button>
        <button
          type="button"
          onClick={copy}
          className="px-2.5 py-1 rounded text-xs font-medium border border-slate-300 bg-white text-slate-700 hover:text-ink transition"
        >
          {copied ? "Copied✓" : "Copy"}
        </button>
        <span className="ml-auto text-[11px] text-muted">
          analysis_date · config · {skillCount} skill{skillCount !== 1 ? "s" : ""}
        </span>
      </div>
      <pre className="p-3 text-xs border rounded bg-slate-50 overflow-auto max-h-[60vh]">{json}</pre>
    </div>
  );
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 -mb-px border-b-2 transition ${active ? "border-violet-400 text-violet-800 font-semibold" : "border-transparent text-muted hover:text-ink"}`}
    >
      {label}
    </button>
  );
}

function AlertCard({ card: c }: { card: any }) {
  const [open, setOpen] = useState(false);
  const cost = Number(c.projected_cost ?? c.sort_value ?? 0);
  const score = c.score ?? c.sort_value;
  const triggers = Array.isArray(c.trigger_types) ? c.trigger_types.join(", ") : "";

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      {/* Header */}
      <div
        className="px-3 py-2.5 cursor-pointer flex items-start justify-between gap-2 hover:bg-slate-50"
        onClick={() => setOpen(o => !o)}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-violet-800 bg-violet-100 px-1.5 py-0.5 rounded">{c.signal_type}</span>
            <span className="text-xs text-muted">Store {c.store_id}{c.store_name ? ` · ${c.store_name}` : ""}</span>
            {triggers && <span className="text-xs text-slate-500">{triggers}</span>}
          </div>
          {c.department && <div className="text-xs text-muted mt-0.5">{c.department}</div>}
          {c.issue && <div className="text-sm font-medium text-ink mt-1 truncate">{c.issue}</div>}
        </div>
        <div className="shrink-0 text-right">
          <div className="text-sm font-semibold text-red-700">£{cost.toLocaleString("en-GB", { maximumFractionDigits: 0 })}</div>
          <div className="text-[10px] text-muted">est. cost</div>
          {score != null && (
            <div className="mt-1">
              <div className="text-sm font-semibold text-violet-700">{Number(score).toLocaleString("en-GB", { maximumFractionDigits: 2 })}</div>
              <div className="text-[10px] text-muted">score</div>
            </div>
          )}
        </div>
      </div>

      {/* Expanded body */}
      {open && (
        <div className="px-3 pb-3 border-t pt-2 space-y-1.5 text-sm">
          {c.explanation        && <p className="text-ink whitespace-pre-line">{c.explanation}</p>}
          {c.cost_if_not_fixed  && <p className="text-xs text-muted whitespace-pre-line">Cost if not fixed: {c.cost_if_not_fixed}</p>}
          {c.recommended_action && <p className="text-xs text-violet-700 font-medium whitespace-pre-line">→ {c.recommended_action}</p>}
          {c.next_steps         && <p className="text-xs text-muted whitespace-pre-line">{c.next_steps}</p>}
        </div>
      )}
    </div>
  );
}
