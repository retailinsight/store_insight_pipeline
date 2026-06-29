import { useState } from "react";
import CustomerSelect from "./pages/CustomerSelect";
import Workbench from "./pages/Workbench";

export default function App() {
  const [client, setClient] = useState<string | null>(null);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-violet-50 border-b border-violet-100 text-ink px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-violet-400" />
            Pipeline Experiments
          </span>
          {client && (
            <span className="text-sm text-muted">
              · client <span className="font-medium text-ink">{client}</span>
            </span>
          )}
        </div>
        {client && (
          <button
            className="text-sm text-muted hover:text-ink underline"
            onClick={() => setClient(null)}
          >
            change customer
          </button>
        )}
      </header>

      <main className="flex-1">
        {!client
          ? <CustomerSelect onSelect={setClient} />
          : <Workbench client={client} />
        }
      </main>
    </div>
  );
}
