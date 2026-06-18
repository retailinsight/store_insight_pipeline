import { useState } from "react";
import { DetectorEntry } from "../lib/api";

// Map signal_type → top-level threshold key in cfg.thresholds.
// Most signal types map directly; "shared" thresholds live under cfg.thresholds.shared.
const SHARED_KEYS = new Set([
  "section",
  "min_lost_sales_value",
]);

function readThreshold(config: any, signalType: string, key: string): any {
  const buckets = config?.detector_config?.thresholds ?? {};
  if (SHARED_KEYS.has(key) && buckets.shared && key in buckets.shared) {
    return buckets.shared[key];
  }
  return buckets[signalType]?.[key];
}

function writeThreshold(config: any, signalType: string, key: string, value: any): any {
  const detectorConfig = { ...(config.detector_config ?? {}) };
  const thresholds = { ...(detectorConfig.thresholds ?? {}) };
  const isShared = SHARED_KEYS.has(key) && thresholds.shared && key in thresholds.shared;
  const bucketKey = isShared ? "shared" : signalType;
  thresholds[bucketKey] = { ...(thresholds[bucketKey] ?? {}), [key]: value };
  detectorConfig.thresholds = thresholds;
  return { ...config, detector_config: detectorConfig };
}

export default function DetectorRow({
  detector,
  config,
  onChange,
}: {
  detector: DetectorEntry;
  config: any;
  onChange: (cfg: any) => void;
}) {
  const enabled: string[] = config?.detectors?.enabled ?? [];
  const isOn = enabled.includes(detector.name);
  const [showDetails, setShowDetails] = useState(false);

  const tablesMap: Record<string, string> = config?.tables ?? {};

  const toggle = () => {
    const next = isOn
      ? enabled.filter(n => n !== detector.name)
      : [...enabled, detector.name];
    onChange({ ...config, detectors: { ...(config.detectors ?? {}), enabled: next } });
  };

  const updateThreshold = (key: string, value: string) => {
    const num = value === "" ? "" : Number(value);
    onChange(writeThreshold(config, detector.signal_type, key, num));
  };

  return (
    <div className={`rounded-xl border p-4 transition ${
      isOn
        ? "bg-violet-50 border-violet-200"
        : "bg-white border-slate-200 opacity-70 hover:opacity-100"
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-sm">{detector.name}</div>
          <div className="text-xs text-muted">{detector.display_name}</div>
        </div>
        <label className="inline-flex items-center cursor-pointer shrink-0">
          <input type="checkbox" className="sr-only peer" checked={isOn} onChange={toggle} />
          <span className="w-10 h-5 bg-slate-300 peer-checked:bg-violet-400 rounded-full relative transition">
            <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition ${isOn ? "translate-x-5" : ""}`} />
          </span>
        </label>
      </div>

      {detector.problem && (
        <p className="text-xs text-muted mt-2 line-clamp-2">{detector.problem}</p>
      )}

      <button
        type="button"
        onClick={() => setShowDetails(s => !s)}
        className="mt-2 text-[11px] font-medium text-violet-700 hover:text-violet-900"
      >
        {showDetails ? "▾ hide details" : "▸ show details"}
      </button>

      {showDetails && (
        <div className="mt-2 space-y-2 text-xs border-t border-slate-200 pt-2">
          {detector.problem && (
            <DetailBlock title="Problem" body={detector.problem} />
          )}
          {detector.baseline && (
            <DetailBlock title="Baseline" body={detector.baseline} />
          )}
          {detector.logic && (
            <DetailBlock title="Logic" body={detector.logic} />
          )}
          {detector.action && (
            <DetailBlock title="Recommended action" body={detector.action} />
          )}

          {detector.data_sources.length > 0 && (
            <div>
              <div className="font-semibold text-ink">Data sources</div>
              <ul className="mt-0.5 space-y-0.5">
                {detector.data_sources.map(ds => (
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
            <span className="font-semibold">Module:</span> <code>{detector.module}</code>
          </div>
        </div>
      )}

      {isOn && detector.thresholds.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {detector.thresholds.map(t => {
            const v = readThreshold(config, detector.signal_type, t.name);
            return (
              <label key={t.name} className="text-xs">
                <span className="block text-muted truncate" title={t.name}>{t.name}</span>
                <input
                  type="number"
                  step="any"
                  value={v ?? ""}
                  placeholder={t.default == null ? "" : String(t.default)}
                  onChange={e => updateThreshold(t.name, e.target.value)}
                  className="mt-0.5 w-full px-2 py-1 border rounded text-sm"
                />
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DetailBlock({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <div className="font-semibold text-ink">{title}</div>
      <p className="text-muted whitespace-pre-line">{body}</p>
    </div>
  );
}
