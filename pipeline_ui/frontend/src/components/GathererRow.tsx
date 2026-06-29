import { useState } from "react";
import { GathererEntry } from "../lib/api";

export default function GathererRow({
  gatherer,
  config,
  onChange,
}: {
  gatherer: GathererEntry;
  config: any;
  onChange: (cfg: any) => void;
}) {
  // A gatherer is "enabled" for a signal type if it appears in cfg.gatherers[signal_type].
  // We toggle across ALL its declared signal types atomically.
  const inAny = gatherer.signal_types.some(st =>
    Array.isArray(config?.gatherers?.[st]) && config.gatherers[st].includes(gatherer.name)
  );
  const inAll = gatherer.signal_types.every(st =>
    Array.isArray(config?.gatherers?.[st]) && config.gatherers[st].includes(gatherer.name)
  );
  const isOn = inAll;
  const mixed = inAny && !inAll;
  const [showDetails, setShowDetails] = useState(false);
  const tablesMap: Record<string, string> = config?.tables ?? {};

  const toggle = () => {
    const nextGatherers = { ...(config.gatherers ?? {}) };
    for (const st of gatherer.signal_types) {
      const list: string[] = Array.isArray(nextGatherers[st]) ? [...nextGatherers[st]] : [];
      const idx = list.indexOf(gatherer.name);
      if (isOn) {
        if (idx >= 0) list.splice(idx, 1);
      } else {
        if (idx < 0) list.push(gatherer.name);
      }
      nextGatherers[st] = list;
    }
    onChange({ ...config, gatherers: nextGatherers });
  };

  return (
    <div className={`rounded-xl border p-4 transition ${
      isOn
        ? "bg-emerald-50 border-emerald-200"
        : "bg-white border-slate-200 opacity-70 hover:opacity-100"
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-sm">{gatherer.name}</div>
          <div className="flex flex-wrap gap-1 mt-1">
            {gatherer.signal_types.map(st => (
              <span key={st} className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium">
                {st}
              </span>
            ))}
          </div>
        </div>
        <label className="inline-flex items-center cursor-pointer shrink-0">
          <input type="checkbox" className="sr-only peer" checked={isOn} onChange={toggle} />
          <span className={`w-10 h-5 rounded-full relative transition ${
            mixed
              ? "bg-amber-300"
              : "bg-slate-300 peer-checked:bg-emerald-400"
          }`}>
            <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition ${isOn ? "translate-x-5" : ""}`} />
          </span>
        </label>
      </div>
      {gatherer.description && (
        <p className="text-xs text-muted mt-2 line-clamp-3">{gatherer.description}</p>
      )}

      <button
        type="button"
        onClick={() => setShowDetails(s => !s)}
        className="mt-2 text-[11px] font-medium text-emerald-700 hover:text-emerald-900"
      >
        {showDetails ? "▾ hide details" : "▸ show details"}
      </button>

      {showDetails && (
        <div className="mt-2 space-y-2 text-xs border-t border-slate-200 pt-2">
          {gatherer.description && (
            <div>
              <div className="font-semibold text-ink">What it does</div>
              <p className="text-muted whitespace-pre-line">{gatherer.description}</p>
            </div>
          )}

          {gatherer.facts_keys.length > 0 && (
            <div>
              <div className="font-semibold text-ink">Facts it adds to each signal</div>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {gatherer.facts_keys.map(k => (
                  <code key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                    {k}
                  </code>
                ))}
              </div>
            </div>
          )}

          {gatherer.data_sources.length > 0 && (
            <div>
              <div className="font-semibold text-ink">Data sources</div>
              <ul className="mt-0.5 space-y-0.5">
                {gatherer.data_sources.map(ds => (
                  <li key={ds.param} className="flex flex-col">
                    <span className="text-ink">{ds.label}</span>
                    <code className="text-[10px] text-muted break-all">
                      {tablesMap[ds.cfg_key] ?? `tables.${ds.cfg_key}`}
                    </code>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="text-[10px] text-muted">
            <span className="font-semibold">Module:</span> <code>{gatherer.module}</code>
          </div>
        </div>
      )}
    </div>
  );
}
