import { useEffect, useMemo, useRef, useState } from "react";
import { api, RunResult } from "../lib/api";

interface Store { store_id: number; store_name: string }

export default function RunPanel({
  client,
  running,
  onRun,
  onReset,
  error,
  result,
  allSignalTypes = [],
  liveLogs = [],
  engines = ["rule_based", "cortex"],
  engine = "rule_based",
  onEngineChange,
}: {
  client: string;
  running: boolean;
  onRun: (analysisDate: string, storeIds: number[], signalTypes: string[]) => void;
  onReset: () => void;
  error: string | null;
  result: RunResult | null;
  allSignalTypes?: string[];
  liveLogs?: string[];
  engines?: string[];
  engine?: string;
  onEngineChange?: (engine: string) => void;
}) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState<string>(today);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  const toggleType = (t: string) =>
    setSelectedTypes(prev => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });

  const [stores, setStores]           = useState<Store[] | null>(null);
  const [storesError, setStoresError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [search, setSearch]           = useState("");
  const [open, setOpen]               = useState(false);

  useEffect(() => {
    setStores(null); setStoresError(null); setSelectedIds(new Set());
    api.stores(client)
      .then(r => setStores(r.stores))
      .catch(e => setStoresError(String(e)));
  }, [client]);

  const filtered = useMemo(() => {
    if (!stores) return [];
    const q = search.trim().toLowerCase();
    if (!q) return stores.slice(0, 50);
    return stores
      .filter(s =>
        s.store_name.toLowerCase().includes(q) ||
        String(s.store_id).includes(q)
      )
      .slice(0, 50);
  }, [stores, search]);

  const selectedStores = useMemo(
    () => (stores ?? []).filter(s => selectedIds.has(s.store_id)),
    [stores, selectedIds],
  );

  const toggle = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="p-5 border-b border-slate-200 bg-violet-50 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-violet-900">Run experiment</h2>
        <button
          onClick={onReset}
          className="text-xs text-muted hover:text-ink underline"
          type="button"
        >
          reset config
        </button>
      </div>

      <label className="block text-sm">
        <span className="block text-xs text-muted">Analysis date (last day of week)</span>
        <input
          type="date"
          value={date}
          onChange={e => setDate(e.target.value)}
          className="mt-0.5 w-full px-2 py-1 border rounded text-sm"
        />
      </label>

      <div className="text-sm">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">
            Stores {selectedIds.size > 0 && <span className="text-ink">({selectedIds.size} selected)</span>}
          </span>
          {selectedIds.size > 0 && (
            <button
              type="button"
              onClick={() => setSelectedIds(new Set())}
              className="text-xs text-muted hover:text-ink underline"
            >
              clear
            </button>
          )}
        </div>

        {storesError && (
          <div className="mt-1 text-xs text-red-600">{storesError}</div>
        )}
        {!stores && !storesError && (
          <div className="mt-1 text-xs text-muted">Loading stores…</div>
        )}

        {stores && (
          <>
            {selectedStores.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1 mb-1">
                {selectedStores.map(s => (
                  <span
                    key={s.store_id}
                    className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-violet-100 text-violet-800 border border-violet-200"
                  >
                    {s.store_name}
                    <button
                      type="button"
                      onClick={() => toggle(s.store_id)}
                      className="text-violet-600 hover:text-violet-900"
                      aria-label={`remove ${s.store_name}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
            <input
              type="text"
              value={search}
              onChange={e => { setSearch(e.target.value); setOpen(true); }}
              onFocus={() => setOpen(true)}
              placeholder="Search by name or ID… (leave empty for whole chain)"
              className="mt-0.5 w-full px-2 py-1 border rounded text-sm"
            />
            {open && (
              <div className="mt-1 max-h-56 overflow-auto border rounded bg-white">
                {filtered.length === 0 && (
                  <div className="px-2 py-2 text-xs text-muted">No matches.</div>
                )}
                {filtered.map(s => {
                  const checked = selectedIds.has(s.store_id);
                  return (
                    <button
                      key={s.store_id}
                      type="button"
                      onClick={() => toggle(s.store_id)}
                      className={`w-full text-left px-2 py-1.5 text-sm flex items-center justify-between gap-2 hover:bg-violet-50 ${
                        checked ? "bg-violet-50" : ""
                      }`}
                    >
                      <span className="truncate">{s.store_name}</span>
                      <span className="text-xs text-muted shrink-0">
                        {checked && "✓ "}{s.store_id}
                      </span>
                    </button>
                  );
                })}
                {!search && stores.length > filtered.length && (
                  <div className="px-2 py-1.5 text-[11px] text-muted border-t">
                    Showing first {filtered.length} of {stores.length} — type to search.
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {allSignalTypes.length > 0 && (
        <div>
          <span className="block text-xs text-muted mb-1">
            Signal types <span className="text-ink">{selectedTypes.size === 0 ? "(all)" : `(${selectedTypes.size} selected)`}</span>
          </span>
          <div className="flex flex-wrap gap-1">
            {allSignalTypes.map(t => {
              const on = selectedTypes.has(t);
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => toggleType(t)}
                  className={`px-2 py-0.5 rounded-full text-xs border font-medium transition ${
                    on ? "bg-violet-600 text-white border-violet-600" : "bg-white text-slate-600 border-slate-300 hover:border-violet-400"
                  }`}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {onEngineChange && (
        <div>
          <span className="block text-xs text-muted mb-1">
            Investigation engine {engine === "mixed" && <span className="text-amber-600">(mixed — applies to all)</span>}
          </span>
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            {engines.map(en => {
              const on = engine === en;
              return (
                <button
                  key={en}
                  type="button"
                  onClick={() => onEngineChange(en)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                    on ? "bg-violet-600 text-white" : "text-slate-600 hover:text-ink"
                  }`}
                >
                  {en}
                </button>
              );
            })}
          </div>
          {engine !== "rule_based" && (
            <p className="mt-1 text-[11px] text-amber-700">
              When any signal uses Cortex, only the top 10 signals by score are investigated (enriched + narrated into cards) — the rest are dropped to bound DB + LLM cost. Runs where every signal is rule-based skip this cap and process all signals.
            </p>
          )}
        </div>
      )}

      <button
        disabled={running}
        onClick={() => onRun(date, Array.from(selectedIds), Array.from(selectedTypes))}
        className="w-full py-2.5 rounded-lg font-semibold text-sm text-violet-900 bg-violet-200 hover:bg-violet-300 transition disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {running ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block h-3 w-3 rounded-full border-2 border-violet-700 border-t-transparent animate-spin" />
            Running…
          </span>
        ) : "▶ Run pipeline"}
      </button>

      {(running || liveLogs.length > 0) && (
        <LiveLog lines={liveLogs} running={running} endRef={logEndRef} />
      )}

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {result && (
        <div className="text-xs text-muted">
          <div>
            {result.counts.signals} signals · {result.counts.enriched} enriched · {result.counts.cards} cards
          </div>
          <div>
            detect {result.timings.detect_ms}ms · score {result.timings.score_ms}ms · facts {result.timings.facts_ms}ms · investigate {result.timings.investigate_ms}ms
          </div>
          {result.error && <div className="text-red-600 mt-1">{result.error}</div>}
        </div>
      )}
    </div>
  );
}

function LiveLog({
  lines,
  running,
  endRef,
}: {
  lines: string[];
  running: boolean;
  endRef: React.RefObject<HTMLDivElement>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll only the log container, not the whole page, to keep the
    // latest line in view without moving the rest of the screen.
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div className="rounded border border-slate-700 bg-slate-900 overflow-hidden">
      <div className="flex items-center justify-between px-2 py-1 bg-slate-800 border-b border-slate-700">
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Pipeline log</span>
        {running && (
          <span className="flex items-center gap-1 text-[10px] text-green-400">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            live
          </span>
        )}
      </div>
      <div ref={scrollRef} className="max-h-52 overflow-auto p-2 font-mono text-[11px] text-slate-200 space-y-0.5">
        {lines.length === 0 && running && (
          <div className="text-slate-500 italic">Waiting for output…</div>
        )}
        {lines.map((l, i) => (
          <div key={i} className={`whitespace-pre-wrap leading-snug ${
            l.includes("ERROR") ? "text-red-400" :
            l.startsWith("[runner]") ? "text-green-300" :
            "text-slate-300"
          }`}>{l}</div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
