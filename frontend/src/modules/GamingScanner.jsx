import { useState } from "react";
import { ExternalLink, Gamepad2, Loader2, Search } from "lucide-react";
import { lookupGamer } from "../lib/api.js";

function Pill({ ok, label }) {
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

function Field({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <p className="text-[11px] text-zinc-400">
      <span className="font-mono text-zinc-600">{label} </span>
      {String(value)}
    </p>
  );
}

export default function GamingScanner({ seed = "" }) {
  const [handle, setHandle] = useState(seed.replace(/^@/, ""));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run(event) {
    event?.preventDefault();
    const tag = handle.trim().replace(/^@/, "");
    if (!tag) return;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupGamer(tag));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix flex items-center gap-1.5">
            <Gamepad2 className="h-3.5 w-3.5" />
            Gaming Scanner
          </p>
          <h2 className="text-sm text-zinc-100">Public gamertag lookup</h2>
          <p className="text-[11px] text-zinc-500 max-w-xl">
            Steam XML, Mojang/Minecraft, Roblox, then public tracker pages. No API keys. Profile
            probes can false-positive on 200 search pages.
          </p>
        </div>
        <form onSubmit={run} className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
            <input
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="Notch, Roblox, gaben…"
              aria-label="Gamertag"
              className="w-full h-8 pl-8 pr-3 rounded-md bg-zinc-950 border border-zinc-800 text-[12px] font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-matrix/50"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !handle.trim()}
            className="h-8 px-3 rounded-md bg-matrix text-slate-950 text-[11px] font-mono uppercase tracking-wider disabled:opacity-40 inline-flex items-center gap-1.5"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Gamepad2 className="h-3.5 w-3.5" />}
            Lookup
          </button>
        </form>
      </div>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-2.5">
          <article className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-medium text-zinc-100">Steam</h3>
              <Pill ok={data.steam?.found} label={data.steam?.found ? "Found" : "No profile"} />
            </div>
            <Field label="persona" value={data.steam?.persona} />
            <Field label="id64" value={data.steam?.steam_id64} />
            <Field label="since" value={data.steam?.member_since} />
            <Field label="state" value={data.steam?.online_state} />
            <Field label="vac" value={data.steam?.found ? (data.steam.vac_banned ? "banned" : "clean") : null} />
            {data.steam?.url && (
              <a href={data.steam.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix">
                Open <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </article>

          <article className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-medium text-zinc-100">Minecraft</h3>
              <Pill ok={data.minecraft?.found} label={data.minecraft?.found ? "Found" : "No profile"} />
            </div>
            <Field label="name" value={data.minecraft?.username} />
            <Field label="uuid" value={data.minecraft?.uuid} />
            <Field label="created" value={data.minecraft?.created_at} />
            {data.minecraft?.url && (
              <a href={data.minecraft.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix">
                NameMC <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </article>

          <article className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-medium text-zinc-100">Roblox</h3>
              <Pill ok={data.roblox?.found} label={data.roblox?.found ? "Found" : "No profile"} />
            </div>
            <Field label="user" value={data.roblox?.username} />
            <Field label="display" value={data.roblox?.display_name} />
            <Field label="id" value={data.roblox?.user_id} />
            <Field label="created" value={data.roblox?.created} />
            {data.roblox?.url && (
              <a href={data.roblox.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix">
                Open <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </article>
        </div>
      )}

      {data?.profiles && (
        <section className="rounded-lg border border-zinc-800 bg-zinc-950/40">
          <p className="px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            Public trackers
          </p>
          {data.profiles.map((row) => (
            <div key={row.id} className="grid grid-cols-[8rem_minmax(0,1fr)_auto_auto] gap-3 items-center px-3 py-2 border-t border-zinc-800/60">
              <span className="text-[12px] text-zinc-200 truncate">{row.platform}</span>
              <span className="text-[11px] font-mono text-zinc-500 truncate">{row.url}</span>
              <Pill ok={row.exists} label={row.state} />
              <a href={row.url} target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-matrix">
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
