import { Search, Loader2, X, PanelLeftClose, PanelLeftOpen } from "lucide-react";

export default function TopBar({
  query,
  onQueryChange,
  searching,
  resultCount,
  collapsed,
  onToggleSidebar,
}) {
  return (
    <header className="h-12 shrink-0 border-b border-zinc-800/80 bg-slate-950/90 backdrop-blur-sm flex items-center gap-2 px-3">
      <button
        type="button"
        onClick={onToggleSidebar}
        className="h-8 w-8 grid place-items-center rounded-md text-zinc-500 hover:text-matrix hover:bg-zinc-900"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
      </button>

      <div className="relative flex-1 max-w-4xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-matrix/80" />
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Global fuzzy search — names, categories, descriptions"
          aria-label="Global fuzzy search"
          className="w-full h-8 pl-9 pr-20 rounded-md bg-zinc-900/80 border border-zinc-800 text-[12px] font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-matrix/50 focus:ring-1 focus:ring-matrix/30"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
          {searching && <Loader2 className="h-3.5 w-3.5 animate-spin text-matrix" />}
          {query && (
            <button
              type="button"
              onClick={() => onQueryChange("")}
              className="text-zinc-500 hover:text-zinc-200"
              title="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline text-[9px] font-mono text-zinc-600 border border-zinc-800 rounded px-1 py-0.5">
            /
          </kbd>
        </div>
      </div>

      {typeof resultCount === "number" && query.trim().length >= 2 && (
        <p className="hidden md:block text-[10px] font-mono text-matrix/80 whitespace-nowrap">
          {resultCount.toLocaleString()} HITS
        </p>
      )}
    </header>
  );
}
