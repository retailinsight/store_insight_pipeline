import { ScorerEntry } from "../lib/api";

interface ScorerRowProps {
  signalType: string;
  config: Record<string, any>;
  onChange: (config: Record<string, any>) => void;
  scorer?: ScorerEntry;
}

// Maps each composite dimension to: human label, which ceiling config key it uses, unit label
const DIMENSIONS: { key: string; label: string; ceilingCfgKey: string | null; unit: string; formula: string; description: string; placeholder: boolean }[] = [
  {
    key: "financial_severity", label: "Financial severity", ceilingCfgKey: "cost_ceilings", unit: "£",
    formula: "min(projected_cost / ceiling, 1)",
    description: "How costly is this alert in £ terms? Projected cost ÷ ceiling — a £2,500 signal against a £5,000 ceiling scores 0.5. Signals at or above the ceiling score 1.0.",
    placeholder: false,
  },
  {
    key: "vs_control_benchmark", label: "VS chain benchmark", ceilingCfgKey: "benchmark_ceilings", unit: "pp",
    formula: "min(|chain_gap_pp| / ceiling, 1)",
    description: "How far below the chain average is this store on this metric? Only fires if the VS_CHAIN trigger is present. A store 10pp below chain against a 20pp ceiling scores 0.5.",
    placeholder: false,
  },
  {
    key: "vs_historical_benchmark", label: "VS last week (WoW)", ceilingCfgKey: "wow_ceilings", unit: "pp",
    formula: "min(|wow_drift_pp| / ceiling, 1)",
    description: "How sharply did this metric deteriorate week-on-week? Only fires if the WOW trigger is present. A 7.5pp drop against a 15pp ceiling scores 0.5.",
    placeholder: false,
  },
  {
    key: "thematic", label: "Thematic", ceilingCfgKey: null, unit: "",
    formula: "placeholder — always 0.5",
    description: "Intended to capture store-level KPI themes (e.g. a store with a known waste problem). Not yet implemented — returns a constant 0.5.",
    placeholder: true,
  },
  {
    key: "historical_recency", label: "Historical recency", ceilingCfgKey: null, unit: "",
    formula: "placeholder — always 0.5",
    description: "Intended to dampen signals for stores that were alerted recently on the same issue. Not yet implemented — returns a constant 0.5.",
    placeholder: true,
  },
  {
    key: "special_cases", label: "Special cases", ceilingCfgKey: null, unit: "",
    formula: "placeholder — always 0.5",
    description: "Intended to capture seasonal or promotional context (e.g. a store in a promo period). Not yet implemented — returns a constant 0.5.",
    placeholder: true,
  },
];

const DEFAULT_WEIGHTS: Record<string, number> = {
  financial_severity: 1.0, vs_control_benchmark: 0.0, vs_historical_benchmark: 0.0,
  thematic: 0.0, historical_recency: 0.0, special_cases: 0.0,
};

export default function ScorerRow({ signalType, config, onChange, scorer }: ScorerRowProps) {
  const scoring = config?.scoring ?? {};

  // ── helpers to patch config immutably ────────────────────────────────────
  const patch = (updates: Record<string, any>) =>
    onChange({ ...config, scoring: { ...scoring, ...updates } });

  const setScoreWeight = (v: string) => {
    const n = parseFloat(v);
    if (!isNaN(n)) patch({ score_weights: { ...(scoring.score_weights ?? {}), [signalType]: n } });
  };

  const setCompositeWeight = (dim: string, v: string) => {
    const n = parseFloat(v);
    if (!isNaN(n)) patch({ composite_weights: { ...DEFAULT_WEIGHTS, ...(scoring.composite_weights ?? {}), [dim]: n } });
  };

  const setCeiling = (cfgKey: string, v: string) => {
    const n = parseFloat(v);
    if (!isNaN(n)) patch({ [cfgKey]: { ...(scoring[cfgKey] ?? {}), [signalType]: n } });
  };

  // ── current values from config ────────────────────────────────────────────
  const scoreWeight: number = scoring?.score_weights?.[signalType] ?? 1.0;
  const compositeWeights: Record<string, number> = { ...DEFAULT_WEIGHTS, ...(scoring?.composite_weights ?? {}) };
  const weightSum = Object.values(compositeWeights).reduce((s, v) => s + v, 0);

  return (
    <div className="space-y-4">

      {/* ── Projected cost formula (read-only) ─────────────────────────── */}
      {scorer && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 space-y-1">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">Projected cost formula</div>
          <code className="text-xs bg-white border border-slate-200 rounded px-1.5 py-0.5 font-mono text-ink inline-block">
            {scorer.formula}
          </code>
          {scorer.description && <div className="text-xs text-muted">{scorer.description}</div>}
        </div>
      )}

      {/* ── score_weight ────────────────────────────────────────────────── */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
        <div className="text-xs font-semibold text-muted uppercase tracking-wider">Score weight</div>
        <div className="text-xs text-muted">
          Scales projected cost before ranking. Raise this to prioritise {signalType} alerts over other types; lower it to deprioritise.
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number" step="0.1" min="0"
            className="w-24 px-2 py-1 border rounded text-sm text-right bg-white"
            value={scoreWeight}
            onChange={e => setScoreWeight(e.target.value)}
          />
          <span className="text-xs text-muted">× projected cost</span>
        </div>
      </div>

      {/* ── Composite dimensions ────────────────────────────────────────── */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider">Composite score dimensions</div>
          <div className={`text-xs font-mono font-semibold ${Math.abs(weightSum - 1) > 0.01 ? "text-red-600" : "text-slate-500"}`}>
            weights sum: {(weightSum * 100).toFixed(0)}%{Math.abs(weightSum - 1) > 0.01 ? " ⚠" : ""}
          </div>
        </div>
        <div className="text-xs text-muted">
          Each dimension produces a 0–1 score. The final score is the weighted sum. Change the weights to experiment with different prioritisation strategies.
        </div>

        <div className="divide-y divide-slate-100 border rounded bg-white overflow-hidden text-xs">
          {DIMENSIONS.map(dim => {
            const w = compositeWeights[dim.key] ?? 0;
            const ceilingVal = dim.ceilingCfgKey ? (scoring?.[dim.ceilingCfgKey]?.[signalType] ?? "") : "";
            return (
              <div key={dim.key} className={`px-3 py-2.5 space-y-1.5 ${w === 0 ? "opacity-50" : ""}`}>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-ink">{dim.label}</span>
                    <span className="ml-2 font-mono text-muted text-[11px]">{dim.formula}</span>
                    <div className="text-muted text-[11px] mt-0.5">{dim.description}</div>
                  </div>
                  {/* Weight input */}
                  <div className="flex items-center gap-1 shrink-0">
                    <input
                      type="number" step="0.05" min="0" max="1"
                      disabled={dim.placeholder}
                      className="w-16 px-1.5 py-0.5 border rounded text-right font-mono bg-white disabled:bg-slate-100 disabled:text-slate-400"
                      value={w}
                      onChange={e => setCompositeWeight(dim.key, e.target.value)}
                    />
                    <span className="text-muted">wt</span>
                  </div>
                </div>
                {/* Ceiling input — only for non-placeholder dims */}
                {!dim.placeholder && dim.ceilingCfgKey && (
                  <div className="flex items-center gap-2 pl-0">
                    <span className="text-muted">ceiling ({dim.unit}):</span>
                    <input
                      type="number" step="any" min="0"
                      placeholder="not set"
                      className="w-24 px-1.5 py-0.5 border rounded text-right font-mono bg-white text-[11px]"
                      value={ceilingVal}
                      onChange={e => dim.ceilingCfgKey && setCeiling(dim.ceilingCfgKey, e.target.value)}
                    />
                    {ceilingVal
                      ? <span className="text-muted text-[11px] font-mono">score = min(value / {ceilingVal}, 1)</span>
                      : <span className="text-amber-600 text-[11px] font-medium">⚠ not set — this dimension scores 0</span>
                    }
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
