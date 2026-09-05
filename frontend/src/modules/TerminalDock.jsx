import { useEffect, useRef, useState } from "react";
import { Globe, Loader2, Play, TerminalSquare } from "lucide-react";
import { runTerminalCommand } from "../lib/api.js";

const COMMANDS = [
  {
    id: "ping",
    label: "ping",
    hint: "ping 4 packets",
    help: "Is this host online? Sends 4 pings and shows reply times.",
    example: "1.1.1.1",
  },
  {
    id: "nslookup",
    label: "nslookup",
    help: "What IP does this domain resolve to?",
    example: "google.com",
  },
  {
    id: "whois",
    label: "whois",
    help: "Who registered this domain? Registrar, dates, name servers.",
    example: "example.com",
  },
];

export default function TerminalDock({ seed = "" }) {
  const [command, setCommand] = useState("ping");
  const [target, setTarget] = useState(seed.trim());
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const outRef = useRef(null);
  const active = COMMANDS.find((item) => item.id === command);

  useEffect(() => {
    if (seed.trim()) setTarget(seed.trim());
  }, [seed]);

  useEffect(() => {
    outRef.current?.scrollTo({ top: outRef.current.scrollHeight });
  }, [output, running]);

  async function execute(event, nextCommand = command, nextTarget = target) {
    event?.preventDefault();
    const host = nextTarget.trim();
    if (!host || running) return;

    setCommand(nextCommand);
    setTarget(host);
    setRunning(true);
    setError(null);
    setMeta({ command: nextCommand, target: host });
    setOutput("");

    try {
      const data = await runTerminalCommand(host, nextCommand);
      const stdout = data.stdout || "";
      const stderr = data.stderr || "";
      setMeta(data);
      setOutput(stdout + (stderr && !stdout.includes(stderr) ? (stdout ? "\n" : "") + stderr : stderr));
    } catch (err) {
      setError(err.message);
      setOutput("");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="h-full flex flex-col min-h-0 p-3 gap-3">
      <div className="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-3">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-matrix">Network diagnostics</p>
          <p className="text-[12px] text-zinc-400 mt-1 max-w-2xl">
            This is not a Linux shell. It runs three safe lookups from the Render server: reachability
            (ping), DNS (nslookup), and registration (whois). Type a domain or IP, pick a command,
            click Execute — or use an example below.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {COMMANDS.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={running}
              onClick={() => execute(null, item.id, item.example)}
              className="text-left rounded-md border border-zinc-800 hover:border-matrix/40 px-2.5 py-1.5 min-w-[9rem] disabled:opacity-50"
            >
              <span className="block text-[11px] font-mono text-matrix">{item.label} {item.example}</span>
              <span className="block text-[10px] text-zinc-500">{item.help}</span>
            </button>
          ))}
        </div>

        <form onSubmit={execute} className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">Command</span>
            <select
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="h-8 rounded-md bg-black border border-zinc-800 px-2 text-[12px] font-mono text-[#39ff14] focus:outline-none focus:border-emerald-500/50"
            >
              {COMMANDS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 flex-1 min-w-[12rem]">
            <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">Domain / IP</span>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder={active?.example || "1.1.1.1"}
              aria-label="Diagnostic target"
              className="h-8 rounded-md bg-black border border-zinc-800 px-2 text-[12px] font-mono text-[#39ff14] placeholder:text-emerald-900 focus:outline-none focus:border-emerald-500/50"
            />
          </label>
          <button
            type="submit"
            disabled={running || !target.trim()}
            className="h-8 px-3 rounded-md bg-[#39ff14] text-black text-[11px] font-mono uppercase tracking-wider inline-flex items-center gap-1.5 disabled:opacity-40"
          >
            {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Execute Command
          </button>
        </form>
      </div>

      <section className="flex-1 min-h-0 rounded-lg border border-emerald-900/50 bg-black overflow-hidden flex flex-col shadow-[0_0_40px_rgba(57,255,20,0.08)]">
        <header className="h-8 shrink-0 px-3 border-b border-emerald-900/40 flex items-center gap-2 bg-[#050805]">
          <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#39ff14]/80" />
          <TerminalSquare className="h-3.5 w-3.5 text-emerald-700 ml-1" />
          <p className="text-[10px] font-mono text-emerald-700 truncate">
            {command} {target.trim() || active?.example}
          </p>
          {meta?.exit_code != null && (
            <span className="ml-auto text-[10px] font-mono text-emerald-800 inline-flex items-center gap-1">
              <Globe className="h-3 w-3" />
              exit {meta.exit_code}
            </span>
          )}
        </header>
        <div ref={outRef} className="relative flex-1 overflow-y-auto">
          <div className="ops-scanlines absolute inset-0 opacity-30" />
          <pre className="relative p-4 font-mono text-[12px] leading-5 text-[#39ff14] whitespace-pre-wrap break-words">
            {error && <span className="text-red-400">{error}</span>}
            {!error && !output && !running && (
              <span className="text-emerald-800">
                Output lands here. Try the ping 1.1.1.1 example — you should see reply times from
                Render’s network, not your home PC.
              </span>
            )}
            {running && !output && <span className="text-emerald-500">Running {command} {target} …</span>}
            {output}
            {running && <span className="inline-block w-2 h-4 ml-0.5 bg-[#39ff14] align-[-2px] animate-pulse" />}
          </pre>
        </div>
      </section>
    </div>
  );
}
