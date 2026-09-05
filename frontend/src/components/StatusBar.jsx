import { useEffect, useState } from "react";
import { Activity, Wifi, WifiOff } from "lucide-react";

export default function StatusBar({ online, module, scrape }) {
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const utc = clock.toISOString().slice(11, 19);

  return (
    <footer className="h-7 shrink-0 border-t border-zinc-800/80 bg-zinc-950 flex items-center gap-3 px-3 font-mono text-[10px] text-zinc-500">
      <span className={`inline-flex items-center gap-1 ${online ? "text-matrix" : "text-rose-400"}`}>
        {online ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
        {online ? "UPLINK 8000" : "NO UPLINK"}
      </span>
      <span className="text-zinc-700">│</span>
      <span className="inline-flex items-center gap-1 uppercase tracking-wider">
        <Activity className="h-3 w-3 text-emerald-500" />
        {module}
      </span>
      <span className="text-zinc-700">│</span>
      <span className={scrape?.running ? "text-amber-400" : "text-zinc-500"}>
        SCRAPE {scrape?.running ? "ACTIVE" : "IDLE"}
      </span>
      <span className="ml-auto text-zinc-400">{utc}Z</span>
    </footer>
  );
}
