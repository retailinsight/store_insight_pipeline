// API client for the Pipeline Experiments backend.

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8002").replace(/\/+$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────

export interface ThresholdField {
  name: string;
  type: string;
  default: number | string | null;
}

export interface DataSource {
  param: string;     // function param name, e.g. "osa"
  label: string;     // human label, e.g. "OSA"
  cfg_key: string;   // resolves under cfg.tables, e.g. "osa"
}

export interface DetectorEntry {
  name: string;                 // e.g. "osa.wow"
  signal_type: string;          // e.g. "OSA"
  display_name: string | null;
  problem: string;
  action: string;
  baseline: string;
  logic: string;
  thresholds: ThresholdField[]; // resolved threshold field defs
  data_sources: DataSource[];
  module: string;
}

export interface GathererEntry {
  name: string;
  signal_types: string[];
  facts_keys: string[];
  description: string;
  data_sources: DataSource[];
  module: string;
}

export interface SkillEntry {
  filename: string;
  rel_path: string;
  signal_type: string;
}

export interface ScorerEntry {
  name:        string;
  signal_type: string;
  formula:     string;
  description: string;
}

export interface Catalog {
  detectors: DetectorEntry[];
  gatherers: GathererEntry[];
  scorers:   ScorerEntry[];
  skills:    SkillEntry[];
  engines:   string[];
  threshold_meta: Record<string, ThresholdField>;
}

export interface RunResult {
  analysis_date: string;
  windows: Record<string, string>;
  signals: any[];
  enriched: any[];
  cards: any[];
  counts: { signals: number; enriched: number; cards: number };
  timings: Record<string, number>;
  logs: string;
  error?: string;
}

// ── Calls ─────────────────────────────────────────────────────────────────

export const api = {
  health:      () => request<{ status: string }>("/health"),
  customers:   () => request<{ customers: string[] }>("/customers"),
  catalog:     () => request<Catalog>("/catalog"),
  config:      (client: string) => request<Record<string, any>>(`/customers/${encodeURIComponent(client)}/config`),
  skills:      (client: string) => request<{ skills: Record<string, { filename: string; content: string }> }>(`/customers/${encodeURIComponent(client)}/skills`),
  stores:      (client: string) => request<{ stores: { store_id: number; store_name: string }[] }>(`/customers/${encodeURIComponent(client)}/stores`),
  run:         (client: string, body: { analysis_date: string; store_ids: number[]; signal_types: string[]; config: Record<string, any> }) =>
    request<RunResult>(`/customers/${encodeURIComponent(client)}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runStream: (
    client: string,
    body: { analysis_date: string; store_ids: number[]; signal_types: string[]; config: Record<string, any> },
    onLog: (line: string) => void,
    signal?: AbortSignal,
  ): Promise<RunResult> => {
    return new Promise((resolve, reject) => {
      fetch(`${BASE}/customers/${encodeURIComponent(client)}/run/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      })
        .then(async res => {
          if (!res.ok) {
            let detail = res.statusText;
            try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
            reject(new Error(`${res.status} ${detail}`));
            return;
          }
          const reader = res.body!.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const parts = buf.split("\n\n");
            buf = parts.pop() ?? "";
            for (const part of parts) {
              const dataLine = part.split("\n").find(l => l.startsWith("data: "));
              if (!dataLine) continue;
              try {
                const evt = JSON.parse(dataLine.slice(6));
                if (evt.type === "log")    { onLog(evt.line); }
                if (evt.type === "error")  { reject(new Error(evt.detail)); }
                if (evt.type === "result") { resolve(evt as RunResult); }
              } catch { /* malformed chunk, ignore */ }
            }
          }
        })
        .catch(reject);
    });
  },
};
