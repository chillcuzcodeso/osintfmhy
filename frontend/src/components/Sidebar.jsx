import {
  Database,
  Crosshair,
  FileSearch,
  Gamepad2,
  Globe,
  Hash,
  Phone,
  Radar,
  Shield,
  ShieldAlert,
  TerminalSquare,
  Wallet,
} from "lucide-react";

const MODULES = [
  { id: "database", label: "Intelligence Database", hint: "FMHY", icon: Database },
  { id: "osint", label: "Active OSINT Tools", hint: "LIVE", icon: Crosshair },
  { id: "scanner", label: "Target Scanner", hint: "UID", icon: Radar },
  { id: "gaming", label: "Gaming Scanner", hint: "TAG", icon: Gamepad2 },
  { id: "scam", label: "Scam Brief", hint: "LURE", icon: ShieldAlert },
  { id: "ip", label: "IP Lookup", hint: "GEO", icon: Globe },
  { id: "phone", label: "Phone Card", hint: "TEL", icon: Phone },
  { id: "discord", label: "Discord / Snowflake", hint: "SNOW", icon: Hash },
  { id: "wallet", label: "Wallet Card", hint: "CHAIN", icon: Wallet },
  { id: "exif", label: "File Meta", hint: "EXIF", icon: FileSearch },
  { id: "terminal", label: "Terminal Dock", hint: "SH", icon: TerminalSquare },
];

export default function Sidebar({ module, onChange, collapsed, stats }) {
  return (
    <aside
      className={`${collapsed ? "w-14" : "w-56"} shrink-0 border-r border-zinc-800/80 bg-zinc-950/90 flex flex-col transition-[width] duration-200`}
    >
      <div className="px-3 py-3 border-b border-zinc-800/80 flex items-center gap-2 min-h-12">
        <div className="h-7 w-7 rounded-md bg-matrix/10 border border-matrix/30 grid place-items-center shrink-0">
          <Shield className="h-3.5 w-3.5 text-matrix" />
        </div>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix">UIP // OPS</p>
            <p className="text-[11px] text-zinc-400 truncate">Low-light research</p>
          </div>
        )}
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {MODULES.map((item) => {
          const Icon = item.icon;
          const active = module === item.id;
          return (
            <button
              key={item.id}
              type="button"
              title={item.label}
              onClick={() => onChange(item.id)}
              className={`w-full flex items-center gap-2.5 rounded-md px-2 py-2 text-left transition-colors ${
                active
                  ? "bg-matrix/10 text-matrix ops-glow"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && (
                <span className="min-w-0 flex-1">
                  <span className="block text-[12px] font-medium leading-tight truncate">{item.label}</span>
                  <span className="block text-[10px] font-mono text-zinc-500 tracking-wider">{item.hint}</span>
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="p-3 border-t border-zinc-800/80 font-mono text-[10px] text-zinc-500 space-y-1">
          <p className="flex justify-between">
            <span>TOOLS</span>
            <span className="text-matrix">{stats.tools.toLocaleString()}</span>
          </p>
          <p className="flex justify-between">
            <span>CATS</span>
            <span className="text-zinc-300">{stats.categories.toLocaleString()}</span>
          </p>
        </div>
      )}
    </aside>
  );
}
