import { Loader2 } from "lucide-react";

export function Field({ label, value }) {
  if (value == null || value === "" || (Array.isArray(value) && !value.length)) return null;
  const text = Array.isArray(value) ? value.join(", ") : String(value);
  return (
    <p className="text-[11px] text-zinc-400">
      <span className="font-mono text-zinc-600">{label} </span>
      <span className="break-all">{text}</span>
    </p>
  );
}

export function Pill({ ok, label }) {
  return (
    <span
      className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${
        ok ? "text-matrix bg-matrix/10 border-matrix/30" : "text-zinc-400 bg-zinc-800/80 border-zinc-700"
      }`}
    >
      {label}
    </span>
  );
}

export function LookupHeader({ icon: Icon, kicker, title, blurb }) {
  return (
    <div>
      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" />
        {kicker}
      </p>
      <h2 className="text-sm text-zinc-100">{title}</h2>
      <p className="text-[11px] text-zinc-500 max-w-2xl">{blurb}</p>
    </div>
  );
}

export function LookupForm({ value, onChange, onSubmit, loading, placeholder, label, icon: Icon, cta = "Lookup" }) {
  return (
    <form onSubmit={onSubmit} className="flex items-center gap-2 w-full sm:w-auto">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className="flex-1 sm:w-72 h-8 px-3 rounded-md bg-zinc-950 border border-zinc-800 text-[12px] font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-matrix/50"
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        className="h-8 px-3 rounded-md bg-matrix text-slate-950 text-[11px] font-mono uppercase tracking-wider disabled:opacity-40 inline-flex items-center gap-1.5"
      >
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : Icon ? <Icon className="h-3.5 w-3.5" /> : null}
        {cta}
      </button>
    </form>
  );
}

export function Card({ children, className = "" }) {
  return (
    <article className={`rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-1.5 ${className}`}>
      {children}
    </article>
  );
}

export function unixMs(value) {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  const ms = n < 1e12 ? n * 1000 : n;
  return new Date(ms).toISOString().replace(".000Z", "Z");
}
