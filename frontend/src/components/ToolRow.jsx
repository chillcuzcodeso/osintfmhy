import { ExternalLink } from "lucide-react";

function StatusDot({ isAlive }) {
  const cls =
    isAlive === 1
      ? "bg-matrix shadow-[0_0_6px_#00ffcc]"
      : isAlive === 0
        ? "bg-rose-500"
        : "bg-zinc-600";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${cls}`} />;
}

export default function ToolRow({ tool, categoryLabel }) {
  return (
    <a
      href={tool.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group grid grid-cols-[auto_minmax(0,1fr)_auto] sm:grid-cols-[auto_9rem_minmax(0,1fr)_minmax(0,1.4fr)_auto] items-center gap-2 px-2.5 py-1.5 border-b border-zinc-800/60 hover:bg-matrix/5"
    >
      <StatusDot isAlive={tool.is_alive} />
      <span className="hidden sm:block text-[10px] font-mono text-zinc-500 truncate">
        {categoryLabel || tool.category || "—"}
      </span>
      <span className="text-[12px] text-zinc-100 truncate group-hover:text-matrix">
        {tool.name}
      </span>
      <span className="hidden sm:block text-[11px] text-zinc-500 truncate">
        {tool.description}
      </span>
      <ExternalLink className="h-3 w-3 text-zinc-600 group-hover:text-matrix shrink-0" />
    </a>
  );
}
