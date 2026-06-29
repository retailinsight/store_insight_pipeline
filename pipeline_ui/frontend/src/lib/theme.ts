// Per–signal-type colour palette. Each entry provides a set of Tailwind
// classes so components stay fully static (Tailwind JIT can see them).
//
// Keep keys UPPER_SNAKE_CASE to match signal_type values.

export interface TypeTheme {
  gradient:   string; // e.g. "from-sky-500 to-blue-600"
  ring:       string; // e.g. "ring-sky-300"
  border:     string; // e.g. "border-sky-300"
  text:       string; // e.g. "text-sky-700"
  softBg:     string; // e.g. "bg-sky-50"
  chipActive: string; // classes to apply when the chip is active
  chipIdle:   string; // classes to apply when the chip is idle (but hoverable)
}

// Pastel per–signal-type palette. Every class is a static string so
// Tailwind's JIT picks them up.
const PALETTES: TypeTheme[] = [
  { // sky
    gradient:   "from-sky-200 to-sky-300",
    ring:       "ring-sky-200",
    border:     "border-sky-200",
    text:       "text-sky-800",
    softBg:     "bg-sky-50",
    chipActive: "bg-sky-100 text-sky-900 border-sky-300",
    chipIdle:   "bg-white text-sky-700 border-sky-100 hover:bg-sky-50",
  },
  { // rose
    gradient:   "from-rose-200 to-rose-300",
    ring:       "ring-rose-200",
    border:     "border-rose-200",
    text:       "text-rose-800",
    softBg:     "bg-rose-50",
    chipActive: "bg-rose-100 text-rose-900 border-rose-300",
    chipIdle:   "bg-white text-rose-700 border-rose-100 hover:bg-rose-50",
  },
  { // amber
    gradient:   "from-amber-200 to-amber-300",
    ring:       "ring-amber-200",
    border:     "border-amber-200",
    text:       "text-amber-800",
    softBg:     "bg-amber-50",
    chipActive: "bg-amber-100 text-amber-900 border-amber-300",
    chipIdle:   "bg-white text-amber-700 border-amber-100 hover:bg-amber-50",
  },
  { // emerald
    gradient:   "from-emerald-200 to-emerald-300",
    ring:       "ring-emerald-200",
    border:     "border-emerald-200",
    text:       "text-emerald-800",
    softBg:     "bg-emerald-50",
    chipActive: "bg-emerald-100 text-emerald-900 border-emerald-300",
    chipIdle:   "bg-white text-emerald-700 border-emerald-100 hover:bg-emerald-50",
  },
  { // violet
    gradient:   "from-violet-200 to-violet-300",
    ring:       "ring-violet-200",
    border:     "border-violet-200",
    text:       "text-violet-800",
    softBg:     "bg-violet-50",
    chipActive: "bg-violet-100 text-violet-900 border-violet-300",
    chipIdle:   "bg-white text-violet-700 border-violet-100 hover:bg-violet-50",
  },
  { // cyan
    gradient:   "from-cyan-200 to-cyan-300",
    ring:       "ring-cyan-200",
    border:     "border-cyan-200",
    text:       "text-cyan-800",
    softBg:     "bg-cyan-50",
    chipActive: "bg-cyan-100 text-cyan-900 border-cyan-300",
    chipIdle:   "bg-white text-cyan-700 border-cyan-100 hover:bg-cyan-50",
  },
  { // lime
    gradient:   "from-lime-200 to-lime-300",
    ring:       "ring-lime-200",
    border:     "border-lime-200",
    text:       "text-lime-800",
    softBg:     "bg-lime-50",
    chipActive: "bg-lime-100 text-lime-900 border-lime-300",
    chipIdle:   "bg-white text-lime-700 border-lime-100 hover:bg-lime-50",
  },
  { // pink
    gradient:   "from-pink-200 to-pink-300",
    ring:       "ring-pink-200",
    border:     "border-pink-200",
    text:       "text-pink-800",
    softBg:     "bg-pink-50",
    chipActive: "bg-pink-100 text-pink-900 border-pink-300",
    chipIdle:   "bg-white text-pink-700 border-pink-100 hover:bg-pink-50",
  },
];

// Deterministic hash so the same signal type always gets the same colour.
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function themeFor(signalType: string): TypeTheme {
  return PALETTES[hash(signalType) % PALETTES.length];
}
