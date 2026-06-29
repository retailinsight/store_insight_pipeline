import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function CustomerSelect({ onSelect }: { onSelect: (c: string) => void }) {
  const [customers, setCustomers] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.customers()
      .then(r => setCustomers(r.customers))
      .catch(e => setError(String(e)));
  }, []);

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-ink mb-2">
        Pick a customer
      </h1>
      <p className="text-muted mb-8">
        Loads the customer's existing YAML config so you can experiment with it.
        Nothing you change here will be saved.
      </p>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg border border-red-200 bg-red-50 text-red-700">
          Failed to load customers: {error}
        </div>
      )}
      {!customers && !error && <div className="text-muted">Loading…</div>}

      {customers && (
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {customers.length === 0 && (
            <li className="text-muted col-span-full">
              No clients found under <code>pipeline/config/clients/</code>.
            </li>
          )}
          {customers.map((c, i) => {
            const pastels = [
              "bg-sky-200",
              "bg-rose-200",
              "bg-amber-200",
              "bg-emerald-200",
              "bg-violet-200",
              "bg-pink-200",
            ];
            const swatch = pastels[i % pastels.length];
            return (
              <li key={c}>
                <button
                  onClick={() => onSelect(c)}
                  className="group w-full text-left rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:bg-slate-50 transition"
                >
                  <div className={`h-1.5 w-10 rounded-full ${swatch} mb-3`} />
                  <div className="font-semibold text-ink">{c}</div>
                  <div className="text-xs text-muted mt-0.5">open workbench →</div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
