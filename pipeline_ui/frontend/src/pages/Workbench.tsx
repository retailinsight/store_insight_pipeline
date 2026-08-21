import { useEffect, useMemo, useState } from "react";
import { api, Catalog, DetectorEntry, RunResult } from "../lib/api";
import { themeFor } from "../lib/theme";
import DetectorRow from "../components/DetectorRow";
import GathererRow from "../components/GathererRow";
import ScorerRow from "../components/ScorerRow";
import RunPanel from "../components/RunPanel";
import StageResults from "../components/StageResults";

export default function Workbench({ client }: { client: string }) {
  const [catalog, setCatalog]   = useState<Catalog | null>(null);
  const [config, setConfig]     = useState<Record<string, any> | null>(null);
  const [skills, setSkills]     = useState<Record<string, { filename: string; content: string }> | null>(null);
  const [error, setError]       = useState<string | null>(null);

  // Snapshot of the loaded YAML so we can reset
  const [pristine, setPristine] = useState<Record<string, any> | null>(null);

  const [running, setRunning]   = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult]     = useState<RunResult | null>(null);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);

  // Exact payload sent to the last run (params + config + skills) for the Run config tab.
  const [runSnapshot, setRunSnapshot] = useState<Record<string, any> | null>(null);

  // Which signal type is currently being configured.
  const [selectedType, setSelectedType] = useState<string | null>(null);

  useEffect(() => {
    setError(null); setConfig(null); setSkills(null); setCatalog(null); setResult(null);
    Promise.all([
      api.catalog(),
      api.config(client),
      api.skills(client),
    ])
      .then(([cat, cfg, sk]) => {
        setCatalog(cat);
        setConfig(cfg);
        setPristine(JSON.parse(JSON.stringify(cfg)));
        setSkills(sk.skills);
      })
      .catch(e => setError(String(e)));
  }, [client]);

  const onReset = () => {
    if (pristine) setConfig(JSON.parse(JSON.stringify(pristine)));
  };

  const onRun = async (analysisDate: string, storeIds: number[], signalTypes: string[]) => {
    if (!config) return;
    setRunning(true); setRunError(null); setResult(null); setLiveLogs([]);
    setRunSnapshot({
      client,
      analysis_date: analysisDate,
      store_ids: storeIds,
      signal_types: signalTypes,
      config: JSON.parse(JSON.stringify(config)),
      skills: skills ? JSON.parse(JSON.stringify(skills)) : {},
    });
    try {
      const r = await api.runStream(
        client,
        { analysis_date: analysisDate, store_ids: storeIds, signal_types: signalTypes, config },
        (line) => setLiveLogs(prev => [...prev, line]),
      );
      setResult(r);
    } catch (e) {
      setRunError(String(e));
    } finally {
      setRunning(false);
    }
  };

  // Group detectors by signal type for display
  const detectorsByType = useMemo(() => {
    if (!catalog) return {} as Record<string, Catalog['detectors']>;
    const map: Record<string, typeof catalog.detectors> = {};
    for (const d of catalog.detectors) {
      (map[d.signal_type] ??= []).push(d);
    }
    return map;
  }, [catalog]);

  // Sorted list of all signal types we know about (from detectors + investigation cfg).
  const allSignalTypes = useMemo(() => {
    const set = new Set<string>();
    Object.keys(detectorsByType).forEach(t => set.add(t));
    // Only add actual signal type keys from investigation (not max_workers)
    const investigation = config?.investigation ?? {};
    Object.keys(investigation).forEach(t => {
      if (t !== 'max_workers') set.add(t);
    });
    return Array.from(set).sort();
  }, [detectorsByType, config]);

  // Auto-select the first signal type once we have them.
  useEffect(() => {
    if (!selectedType && allSignalTypes.length > 0) {
      setSelectedType(allSignalTypes[0]);
    }
  }, [allSignalTypes, selectedType]);

  // Count enabled detectors per signal type (for the tab badge).
  const enabledByType = useMemo(() => {
    const counts: Record<string, number> = {};
    const enabled: string[] = config?.detectors?.enabled ?? [];
    for (const d of catalog?.detectors ?? []) {
      if (enabled.includes(d.name)) {
        counts[d.signal_type] = (counts[d.signal_type] ?? 0) + 1;
      }
    }
    return counts;
  }, [catalog, config]);

  if (error)            return <div className="p-6 text-red-600">{error}</div>;
  if (!catalog || !config) return <div className="p-6 text-muted">Loading config and catalog…</div>;

  // Rows visible for the selected signal type.
  const typeDetectors = selectedType ? (detectorsByType[selectedType] ?? []) : [];
  const typeGatherers = selectedType
    ? catalog.gatherers.filter(g => g.signal_types.includes(selectedType))
    : [];
  const typeSkill     = selectedType ? (skills?.[selectedType] ?? null) : null;
  const typeEngine    = selectedType ? (config.investigation?.[selectedType]?.engine ?? "rule_based") : "rule_based";

  const setEngine = (engine: string) => {
    if (!selectedType) return;
    setConfig({
      ...config,
      investigation: {
        ...(config.investigation ?? {}),
        [selectedType]: { ...(config.investigation?.[selectedType] ?? {}), engine },
      },
    });
  };

  // Global engine across all signal types: uniform value, or "mixed".
  const globalEngine = (() => {
    const engines = allSignalTypes.map(t => config.investigation?.[t]?.engine ?? "rule_based");
    if (engines.length === 0) return "rule_based";
    return engines.every(e => e === engines[0]) ? engines[0] : "mixed";
  })();

  // Apply one engine to every signal type's investigation config.
  const setAllEngines = (engine: string) => {
    const investigation = { ...(config.investigation ?? {}) };
    for (const t of allSignalTypes) {
      investigation[t] = { ...(investigation[t] ?? {}), engine };
    }
    setConfig({ ...config, investigation });
  };

  const setSkillContent = (content: string) => {
    if (!selectedType || !skills || !skills[selectedType]) return;
    setSkills({ ...skills, [selectedType]: { ...skills[selectedType], content } });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-0 min-h-[calc(100vh-49px)]">
      <div className="overflow-y-auto">
        {/* Signal-type picker bar */}
        <div className="sticky top-0 z-10 bg-[#f7f6f2]/90 backdrop-blur-md border-b border-slate-200 px-6 py-3">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-muted mb-2">Signal type</div>
          <div className="flex flex-wrap gap-2">
            {allSignalTypes.map(t => {
              const active = t === selectedType;
              const count  = enabledByType[t] ?? 0;
              const total  = detectorsByType[t]?.length ?? 0;
              const th     = themeFor(t);
              return (
                <button
                  key={t}
                  onClick={() => setSelectedType(t)}
                  className={`px-3.5 py-1.5 rounded-full text-sm border font-medium transition ${
                    active ? th.chipActive : th.chipIdle
                  }`}
                >
                  {t}
                  <span className={`ml-2 text-xs font-normal ${active ? "text-white/80" : "text-muted"}`}>
                    {count}/{total}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-6 space-y-6">
          {!selectedType && <div className="text-muted">Pick a signal type to configure.</div>}

          {selectedType && (() => {
            const th = themeFor(selectedType);
            const granularity = typeDetectors[0]?.granularity ?? "Not specified";
            return (
            <>
              <div className={`rounded-xl border ${th.border} ${th.softBg} px-5 py-3 flex items-center gap-3`}>
                <div className={`h-2.5 w-2.5 rounded-full bg-gradient-to-r ${th.gradient}`} />
                <div className={`font-semibold ${th.text}`}>{selectedType}</div>
                <div className="text-xs text-muted">
                  Signal grain: {granularity}
                </div>
                <div className="text-xs text-muted">
                  {(enabledByType[selectedType] ?? 0)}/{(detectorsByType[selectedType]?.length ?? 0)} detectors enabled
                </div>
              </div>

              <Section
                title={`${selectedType} detectors`}
                subtitle="Toggle and tune thresholds. Disabled detectors won’t produce signals of this type."
                accentGradient={th.gradient}
              >
                {typeDetectors.length === 0 && (
                  <div className="text-sm text-muted">No detectors produce this signal type.</div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {typeDetectors.map((d: DetectorEntry) => (
                    <DetectorRow key={d.name} detector={d} config={config} onChange={setConfig} />
                  ))}
                </div>
              </Section>

              <Section title="Scorer" subtitle="Score-weight multiplier, composite score dimensions and ceilings for this signal type." accentGradient="from-slate-200 to-slate-300">
                <ScorerRow
                  signalType={selectedType}
                  config={config}
                  onChange={setConfig}
                  scorer={catalog.scorers?.find(s => s.signal_type === selectedType)}
                />
              </Section>

              <Section
                title={`${selectedType} fact gatherers`}
                subtitle="Only gatherers that enrich this signal type are shown."
                accentGradient={th.gradient}
              >
                {typeGatherers.length === 0 && (
                  <div className="text-sm text-muted">No gatherers enrich this signal type.</div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {typeGatherers.map(g => (
                    <GathererRow key={g.name} gatherer={g} config={config} onChange={setConfig} />
                  ))}
                </div>
              </Section>

              <Section
                title={`${selectedType} investigation`}
                subtitle="Narrative engine and skill markdown for this signal type."
                accentGradient={th.gradient}
              >
                <div className="flex items-center gap-3 mb-3">
                  <label className="text-xs text-muted">Engine</label>
                  <select
                    value={typeEngine}
                    onChange={e => setEngine(e.target.value)}
                    className="px-2 py-1 border rounded text-sm"
                  >
                    {catalog.engines.map(en => <option key={en} value={en}>{en}</option>)}
                  </select>
                </div>
                {typeSkill ? (
                  <div>
                    <div className="text-xs text-muted mb-1">
                      Skill markdown (<code>{typeSkill.filename}</code>) — in-memory edit only
                    </div>
                    <textarea
                      className="w-full min-h-[260px] font-mono text-xs p-2 border rounded"
                      value={typeSkill.content}
                      onChange={e => setSkillContent(e.target.value)}
                    />
                  </div>
                ) : (
                  <div className="text-sm text-muted">No skill file found for {selectedType}.</div>
                )}
              </Section>

            </>
            );
          })()}
        </div>
      </div>

      <aside className="border-l border-slate-200 bg-white overflow-y-auto">
        <RunPanel
          client={client}
          running={running}
          onRun={onRun}
          onReset={onReset}
          error={runError}
          result={result}
          allSignalTypes={allSignalTypes}
          liveLogs={liveLogs}
          engines={catalog.engines}
          engine={globalEngine}
          onEngineChange={setAllEngines}
        />
        {result && <StageResults result={result} runConfig={runSnapshot} />}
      </aside>
    </div>
  );
}

function Section({ title, subtitle, children, accentGradient }: { title: string; subtitle?: string; children: React.ReactNode; accentGradient?: string }) {
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-5 relative overflow-hidden">
      {accentGradient && (
        <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${accentGradient}`} />
      )}
      <h2 className="text-lg font-semibold mb-1">{title}</h2>
      {subtitle && <p className="text-sm text-muted mb-4">{subtitle}</p>}
      {children}
    </section>
  );
}
