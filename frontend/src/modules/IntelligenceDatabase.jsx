import { useEffect, useMemo, useRef, useState } from "react";
import {
  DatabaseBackup,
  ExternalLink,
  FolderTree,
  Hash,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";
import { searchCatalog } from "../lib/api.js";

function statusLabel(isAlive) {
  if (isAlive === 1) return { text: "Online", className: "text-matrix bg-matrix/10 border-matrix/30" };
  if (isAlive === 0) return { text: "Dead", className: "text-rose-400 bg-rose-500/10 border-rose-500/30" };
  return { text: "Unchecked", className: "text-zinc-400 bg-zinc-800/80 border-zinc-700" };
}

function groupSearchHits(results) {
  const groups = new Map();
  for (const tool of results) {
    const key = tool.category_id ?? tool.category ?? "uncategorized";
    if (!groups.has(key)) {
      groups.set(key, {
        id: key,
        name: tool.category || "Uncategorized",
        parent: tool.parent_name || null,
        headerLevel: tool.header_level || 2,
        source: tool.source_file || "",
        tools: [],
      });
    }
    groups.get(key).tools.push(tool);
  }

  return [...groups.values()].sort((a, b) => {
    const left = `${a.parent || ""}${a.name}`.toLocaleLowerCase();
    const right = `${b.parent || ""}${b.name}`.toLocaleLowerCase();
    return left.localeCompare(right);
  });
}

function ToolCard({ tool }) {
  const status = statusLabel(tool.is_alive);
  return (
    <article className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 flex flex-col gap-2 hover:border-matrix/25 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-[13px] font-medium text-zinc-100 leading-snug">{tool.name}</h4>
        <span
          className={`shrink-0 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${status.className}`}
        >
          {status.text}
        </span>
      </div>
      <p className="text-[11px] text-zinc-500 leading-relaxed line-clamp-2 min-h-[2.2em]">
        {tool.description || "No description in wiki entry."}
      </p>
      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono text-zinc-600 truncate">{tool.source_file}</span>
        <a
          href={tool.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 h-7 px-2.5 rounded-md bg-matrix/10 border border-matrix/30 text-[10px] font-mono uppercase tracking-wider text-matrix hover:bg-matrix hover:text-slate-950"
        >
          Open
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </article>
  );
}

export default function IntelligenceDatabase({
  query,
  catalog,
  catalogError,
  onRefresh,
  onScrape,
  scraping,
  onSearchState,
}) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeGroup, setActiveGroup] = useState("all");
  const requestId = useRef(0);

  const q = query.trim();

  useEffect(() => {
    if (q.length < 1) {
      requestId.current += 1;
      setResults([]);
      setError(null);
      setLoading(false);
      onSearchState?.({ searching: false, resultCount: null, error: null });
      return undefined;
    }

    const id = ++requestId.current;
    const timer = setTimeout(async () => {
      setLoading(true);
      onSearchState?.({ searching: true, resultCount: null, error: null });
      try {
        const data = await searchCatalog(q, 500);
        if (requestId.current !== id) return;
        const hits = data.results || [];
        setResults(hits);
        setError(null);
        setActiveGroup("all");
        onSearchState?.({
          searching: false,
          resultCount: data.count ?? hits.length,
          error: null,
          online: true,
        });
      } catch (err) {
        if (requestId.current !== id) return;
        setResults([]);
        setError(err.message);
        onSearchState?.({
          searching: false,
          resultCount: 0,
          error: err.message,
          online: false,
        });
      } finally {
        if (requestId.current === id) setLoading(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [q, onSearchState]);

  const groups = useMemo(() => groupSearchHits(results), [results]);
  const visibleGroups = useMemo(() => {
    if (activeGroup === "all") return groups;
    return groups.filter((group) => String(group.id) === String(activeGroup));
  }, [groups, activeGroup]);

  return (
    <div className="h-full flex min-h-0">
      <div className="w-52 shrink-0 border-r border-zinc-800/80 bg-zinc-950/50 flex flex-col min-h-0">
        <div className="px-2.5 py-2 border-b border-zinc-800/80">
          <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500 flex items-center gap-1.5">
            <FolderTree className="h-3 w-3 text-matrix" />
            Headers
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
          <button
            type="button"
            onClick={() => setActiveGroup("all")}
            className={`w-full text-left px-2 py-1 rounded text-[11px] font-mono ${
              activeGroup === "all" ? "bg-matrix/10 text-matrix" : "text-zinc-400 hover:bg-zinc-900"
            }`}
          >
            ALL / {results.length.toLocaleString()}
          </button>
          {groups.map((group) => (
            <button
              key={group.id}
              type="button"
              onClick={() => setActiveGroup(String(group.id))}
              className={`w-full text-left px-2 py-1.5 rounded leading-tight ${
                String(activeGroup) === String(group.id)
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "text-zinc-400 hover:bg-zinc-900"
              }`}
            >
              {group.parent && (
                <span className="block text-[9px] font-mono text-zinc-600 truncate">{group.parent}</span>
              )}
              <span className="block text-[11px] truncate">{group.name}</span>
              <span className="block text-[9px] font-mono text-zinc-600">{group.tools.length}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <div className="h-9 shrink-0 px-3 border-b border-zinc-800/80 flex items-center gap-2">
          <p className="text-[11px] font-mono text-zinc-400 truncate">
            <span className="text-matrix">FMHY</span>
            {" // "}
            {q ? `SEARCH /api/search?q=${q}` : "AWAITING QUERY"}
            {q ? <span className="text-zinc-600"> · {results.length.toLocaleString()} matches</span> : null}
          </p>
          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={onRefresh}
              className="h-6 px-2 rounded text-[10px] font-mono text-zinc-400 hover:text-matrix hover:bg-zinc-900 inline-flex items-center gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              SYNC
            </button>
            <button
              type="button"
              onClick={() => onScrape(false)}
              disabled={scraping}
              className="h-6 px-2 rounded text-[10px] font-mono text-zinc-950 bg-matrix/90 hover:bg-matrix inline-flex items-center gap-1 disabled:opacity-50"
            >
              {scraping ? <Loader2 className="h-3 w-3 animate-spin" /> : <DatabaseBackup className="h-3 w-3" />}
              INGEST
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-5">
          {catalogError && (
            <p className="text-[12px] font-mono text-rose-400">Uplink issue: {catalogError}</p>
          )}

          {!q && (catalog.count || 0) === 0 && (
            <div className="h-full min-h-48 grid place-items-center text-center px-6">
              <div className="max-w-md">
                <DatabaseBackup className="h-6 w-6 text-matrix mx-auto mb-3" />
                <p className="text-sm text-zinc-200">FMHY wiki is not on this server yet</p>
                <p className="mt-1 text-[12px] text-zinc-500">
                  Search looks through a local copy of the FreeMediaHeckYeah lists. Render starts
                  empty — click <span className="text-matrix">INGEST</span> once and wait 1–3
                  minutes. Then search for things like <span className="font-mono">ublock</span> or{" "}
                  <span className="font-mono">vpn</span>.
                </p>
                <button
                  type="button"
                  onClick={() => onScrape(false)}
                  disabled={scraping}
                  className="mt-4 h-8 px-3 rounded-md bg-matrix text-slate-950 text-[11px] font-mono uppercase tracking-wider inline-flex items-center gap-1.5 disabled:opacity-50"
                >
                  {scraping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <DatabaseBackup className="h-3.5 w-3.5" />}
                  {scraping ? "Downloading wiki…" : "Ingest FMHY now"}
                </button>
              </div>
            </div>
          )}

          {!q && (catalog.count || 0) > 0 && (
            <div className="h-full min-h-48 grid place-items-center text-center px-6">
              <div>
                <Search className="h-6 w-6 text-matrix mx-auto mb-3" />
                <p className="text-sm text-zinc-200">Search the FMHY catalog</p>
                <p className="mt-1 text-[12px] text-zinc-500 max-w-md">
                  Type in the bar at the top. Try <span className="font-mono">ublock</span>,{" "}
                  <span className="font-mono">youtube</span>, or <span className="font-mono">vpn</span>.
                </p>
                <p className="mt-3 text-[10px] font-mono text-zinc-600">
                  {(catalog.count || 0).toLocaleString()} indexed tools
                  {catalog.category_count ? ` · ${catalog.category_count} headers` : ""}
                </p>
              </div>
            </div>
          )}

          {q && loading && (
            <p className="text-[12px] font-mono text-zinc-500 inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-matrix" />
              Scanning catalog for “{q}” …
            </p>
          )}

          {q && error && (
            <p className="text-[12px] font-mono text-rose-400">Search failed: {error}</p>
          )}

          {q && !loading && !error && groups.length === 0 && (
            <div className="text-[12px] text-zinc-500 space-y-2">
              <p className="font-mono">No tools matched “{q}”.</p>
              {(catalog.count || 0) === 0 && (
                <p>
                  The catalog is empty. Click <span className="text-matrix">INGEST</span> first,
                  wait until the sidebar tool count is above 0, then search again.
                </p>
              )}
            </div>
          )}

          {q &&
            visibleGroups.map((group) => (
              <section key={group.id}>
                <header className="mb-2 flex items-end gap-2 border-b border-zinc-800/80 pb-1.5">
                  <Hash className="h-3.5 w-3.5 text-matrix mb-0.5" />
                  <div className="min-w-0">
                    {group.parent && (
                      <p className="text-[10px] font-mono uppercase tracking-wider text-zinc-600 truncate">
                        {group.parent}
                      </p>
                    )}
                    <h3 className="text-[13px] font-medium text-zinc-100 leading-tight">
                      {group.headerLevel >= 3 ? "###" : "##"} {group.name}
                    </h3>
                  </div>
                  <span className="ml-auto text-[10px] font-mono text-zinc-600">
                    {group.tools.length} · {group.source.replace(".md", "")}
                  </span>
                </header>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                  {group.tools.map((tool) => (
                    <ToolCard key={`${tool.id}-${tool.category_id}`} tool={tool} />
                  ))}
                </div>
              </section>
            ))}
        </div>
      </div>
    </div>
  );
}
