import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, Loader2, Radar, Search, ShieldAlert } from "lucide-react";
import { openUsernameScanStream } from "../lib/api.js";

const SEED_PLATFORMS = [
  { id: "github", name: "GitHub" },
  { id: "gitlab", name: "GitLab" },
  { id: "bitbucket", name: "Bitbucket" },
  { id: "reddit", name: "Reddit" },
  { id: "x", name: "X / Twitter" },
  { id: "instagram", name: "Instagram" },
  { id: "pinterest", name: "Pinterest" },
  { id: "youtube", name: "YouTube" },
  { id: "tiktok", name: "TikTok" },
  { id: "twitch", name: "Twitch" },
  { id: "steam", name: "Steam" },
  { id: "medium", name: "Medium" },
  { id: "devto", name: "Dev.to" },
  { id: "hackernews", name: "Hacker News" },
  { id: "keybase", name: "Keybase" },
  { id: "soundcloud", name: "SoundCloud" },
  { id: "telegram", name: "Telegram" },
  { id: "flickr", name: "Flickr" },
  { id: "tumblr", name: "Tumblr" },
  { id: "vimeo", name: "Vimeo" },
];

function emptyRows(platforms) {
  return platforms.map((platform) => ({
    id: platform.id,
    platform: platform.name,
    url: null,
    status_code: null,
    exists: false,
    state: "queued",
    error: null,
  }));
}

function StateBadge({ state }) {
  const map = {
    queued: "text-zinc-500 bg-zinc-900 border-zinc-800",
    scanning: "text-amber-300 bg-amber-500/10 border-amber-500/30",
    found: "text-matrix bg-matrix/10 border-matrix/30",
    absent: "text-zinc-400 bg-zinc-800/80 border-zinc-700",
    uncertain: "text-sky-300 bg-sky-500/10 border-sky-500/30",
  };
  const label = {
    queued: "Queued",
    scanning: "Scanning",
    found: "Found",
    absent: "No profile",
    uncertain: "Uncertain",
  };
  return (
    <span className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${map[state] || map.queued}`}>
      {label[state] || state}
    </span>
  );
}

export default function TargetScanner({ seed = "" }) {
  const [handle, setHandle] = useState(seed.replace(/^@/, ""));
  const [rows, setRows] = useState(() => emptyRows(SEED_PLATFORMS));
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const stopRef = useRef(null);

  useEffect(() => {
    return () => stopRef.current?.();
  }, []);

  function applySeed(next) {
    setRows(
      emptyRows(next).map((row) => ({
        ...row,
        state: "scanning",
      })),
    );
  }

  function startScan(event) {
    event?.preventDefault();
    const target = handle.trim().replace(/^@/, "");
    if (!target) return;

    stopRef.current?.();
    setError(null);
    setSummary(null);
    setScanning(true);
    applySeed(SEED_PLATFORMS);

    stopRef.current = openUsernameScanStream(target, {
      onStart: (payload) => {
        if (payload.platforms?.length) applySeed(payload.platforms);
      },
      onResult: (item) => {
        setRows((prev) =>
          prev.map((row) => (row.id === item.id ? { ...row, ...item } : row)),
        );
      },
      onDone: (payload) => {
        setSummary(payload);
        setScanning(false);
        stopRef.current = null;
      },
      onError: (err) => {
        setError(err.message);
        setScanning(false);
        stopRef.current = null;
      },
    });
  }

  const stats = useMemo(() => {
    const found = rows.filter((row) => row.exists).length;
    const resolved = rows.filter((row) => row.state !== "queued" && row.state !== "scanning").length;
    return { found, resolved, total: rows.length };
  }, [rows]);

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="px-4 py-3 border-b border-zinc-800/80 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix flex items-center gap-1.5">
            <Radar className="h-3.5 w-3.5" />
            Target Scanner
          </p>
          <h2 className="text-sm text-zinc-100">Public username occupancy</h2>
          <p className="text-[11px] text-zinc-500 max-w-xl">
            Probes known profile URLs in parallel. HTTP 200 is logged as an existing account.
          </p>
        </div>
        <form onSubmit={startScan} className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
            <input
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="username"
              aria-label="Target handle"
              className="w-full h-8 pl-8 pr-3 rounded-md bg-zinc-950 border border-zinc-800 text-[12px] font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-matrix/50"
            />
          </div>
          <button
            type="submit"
            disabled={scanning || !handle.trim()}
            className="h-8 px-3 rounded-md bg-matrix text-slate-950 text-[11px] font-mono uppercase tracking-wider disabled:opacity-40 inline-flex items-center gap-1.5"
          >
            {scanning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Radar className="h-3.5 w-3.5" />}
            Scan
          </button>
        </form>
      </div>

      <div className="h-8 px-4 border-b border-zinc-800/80 flex items-center gap-3 font-mono text-[10px] text-zinc-500">
        <span className={scanning ? "text-amber-300" : "text-zinc-500"}>
          {scanning ? "LIVE" : "IDLE"}
        </span>
        <span className="text-zinc-700">│</span>
        <span>
          {stats.resolved}/{stats.total} resolved
        </span>
        <span className="text-zinc-700">│</span>
        <span className="text-matrix">{stats.found} found</span>
        {summary && (
          <>
            <span className="text-zinc-700">│</span>
            <span>done @{summary.handle}</span>
          </>
        )}
      </div>

      {error && (
        <p className="px-4 py-2 text-[12px] font-mono text-rose-400 flex items-center gap-2">
          <ShieldAlert className="h-3.5 w-3.5" />
          {error}
        </p>
      )}

      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => (
          <div
            key={row.id}
            className="grid grid-cols-[minmax(0,8rem)_minmax(0,1fr)_auto_auto] items-center gap-3 px-4 py-2 border-b border-zinc-800/60"
          >
            <span className="text-[12px] text-zinc-200 truncate">{row.platform}</span>
            <span className="text-[11px] font-mono text-zinc-500 truncate">
              {row.url || "awaiting probe"}
            </span>
            <StateBadge state={row.state === "queued" && scanning ? "scanning" : row.state} />
            {row.exists && row.url ? (
              <a
                href={row.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 h-7 px-2 rounded-md border border-matrix/30 text-[10px] font-mono uppercase text-matrix hover:bg-matrix hover:text-slate-950"
              >
                Open
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : (
              <span className="text-[10px] font-mono text-zinc-600 w-[4.2rem] text-right">
                {row.status_code ?? "—"}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
