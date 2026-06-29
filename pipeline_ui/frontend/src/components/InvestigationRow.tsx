import { useState } from "react";

export default function InvestigationRow({
  engines,
  skills,
  config,
  onChange,
  onSkillsChange,
}: {
  engines: string[];
  skills: Record<string, { filename: string; content: string }>;
  config: any;
  onChange: (cfg: any) => void;
  onSkillsChange: (skills: Record<string, { filename: string; content: string }>) => void;
}) {
  const investigation = config.investigation ?? {};
  const signalTypes = Object.keys(investigation);
  const [openType, setOpenType] = useState<string | null>(null);

  const setEngine = (sigType: string, engine: string) => {
    onChange({
      ...config,
      investigation: {
        ...(config.investigation ?? {}),
        [sigType]: { ...(config.investigation?.[sigType] ?? {}), engine },
      },
    });
  };

  const setSkill = (sigType: string, content: string) => {
    const entry = skills[sigType];
    if (!entry) return;
    onSkillsChange({ ...skills, [sigType]: { ...entry, content } });
    // Note: backend doesn't accept skill content in cfg override (skills are loaded
    // from disk by the investigation engine). Edits here are display-only for v1.
  };

  return (
    <div className="space-y-2">
      {signalTypes.map(sigType => {
        const entry = investigation[sigType] ?? {};
        const skill = skills[sigType];
        const open = openType === sigType;
        return (
          <div key={sigType} className="border rounded-lg bg-white">
            <button
              type="button"
              className="w-full flex items-center justify-between px-4 py-2 text-left"
              onClick={() => setOpenType(open ? null : sigType)}
            >
              <div>
                <div className="text-sm font-medium">{sigType}</div>
                <div className="text-xs text-muted">
                  engine: <span className="text-ink">{entry.engine ?? "rule_based"}</span>
                  {skill && <> · skill: <span className="text-ink">{skill.filename}</span></>}
                </div>
              </div>
              <span className="text-muted text-sm">{open ? "▲" : "▼"}</span>
            </button>

            {open && (
              <div className="border-t p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <label className="text-xs text-muted">Engine</label>
                  <select
                    value={entry.engine ?? "rule_based"}
                    onChange={e => setEngine(sigType, e.target.value)}
                    className="px-2 py-1 border rounded text-sm"
                  >
                    {engines.map(en => <option key={en} value={en}>{en}</option>)}
                  </select>
                </div>

                {skill ? (
                  <div>
                    <div className="text-xs text-muted mb-1">
                      Skill markdown (<code>{skill.filename}</code>) — in-memory edit only
                    </div>
                    <textarea
                      className="w-full min-h-[200px] font-mono text-xs p-2 border rounded"
                      value={skill.content}
                      onChange={e => setSkill(sigType, e.target.value)}
                    />
                  </div>
                ) : (
                  <div className="text-xs text-muted">No skill file found for {sigType}.</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
