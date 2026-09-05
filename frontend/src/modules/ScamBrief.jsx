import { useState } from "react";
import { ExternalLink, Loader2, ShieldAlert } from "lucide-react";
import { analyzeScam } from "../lib/api.js";

function List({ title, items }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">{title}</p>
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item} className="text-[12px] font-mono text-zinc-300 break-all">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ScamBrief() {
  const [text, setText] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run(event) {
    event.preventDefault();
    if (text.trim().length < 4) return;
    setLoading(true);
    setError(null);
    try {
      setData(await analyzeScam(text.trim()));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const domain = data?.domain;
  const artifacts = data?.artifacts;

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div>
        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix flex items-center gap-1.5">
          <ShieldAlert className="h-3.5 w-3.5" />
          Scam Brief
        </p>
        <h2 className="text-sm text-zinc-100">Infrastructure report from a lure</h2>
        <p className="text-[11px] text-zinc-500 max-w-2xl">
          Paste a shady URL or the text of a scam SMS/email. This maps domains, wallets, DNS, RDAP,
          TLS, certificates, Wayback, and public blocklists. It does not spoof, message, or impersonate
          anyone.
        </p>
      </div>

      <form onSubmit={run} className="space-y-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={"Your account is locked. Visit https://paypa1-secure.example/login\nSend USDT to T...."}
          className="w-full rounded-md bg-zinc-950 border border-zinc-800 p-3 text-[12px] font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-matrix/50"
        />
        <button
          type="submit"
          disabled={loading || text.trim().length < 4}
          className="h-8 px-3 rounded-md bg-matrix text-slate-950 text-[11px] font-mono uppercase tracking-wider disabled:opacity-40 inline-flex items-center gap-1.5"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldAlert className="h-3.5 w-3.5" />}
          Build brief
        </button>
      </form>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <div className="space-y-3">
          <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2.5">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
              <List title="URLs" items={artifacts.urls} />
              {!artifacts.urls?.length && <p className="text-[11px] text-zinc-600">No URLs</p>}
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
              <List title="Domains" items={artifacts.domains} />
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3">
              <List title="Emails" items={artifacts.emails} />
              <List title="Phones" items={artifacts.phones} />
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-2">
              <List title="BTC" items={artifacts.wallets?.btc} />
              <List title="ETH" items={artifacts.wallets?.eth} />
              <List title="TRON" items={artifacts.wallets?.tron} />
              {data.wallets?.map((wallet) => (
                <a
                  key={wallet.address}
                  href={wallet.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[10px] font-mono text-matrix"
                >
                  {wallet.chain} explorer <ExternalLink className="h-3 w-3" />
                </a>
              ))}
            </div>
          </section>

          {domain && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-[13px] text-zinc-100">
                  Primary host <span className="font-mono text-matrix">{domain.host}</span>
                </h3>
                {domain.urlhaus?.listed && (
                  <span className="text-[9px] font-mono uppercase text-rose-400 border border-rose-500/40 px-1.5 py-0.5 rounded">
                    URLhaus listed
                  </span>
                )}
              </div>
              {domain.error && <p className="text-[12px] text-rose-400">{domain.error}</p>}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] text-zinc-400">
                <div>
                  <p className="font-mono text-zinc-600 uppercase text-[10px] mb-1">Registration</p>
                  <p>Registered {domain.rdap?.registered || "—"}</p>
                  <p>Expires {domain.rdap?.expires || "—"}</p>
                  <p>NS {domain.rdap?.nameservers?.join(", ") || "—"}</p>
                </div>
                <div>
                  <p className="font-mono text-zinc-600 uppercase text-[10px] mb-1">TLS</p>
                  <p>CN {domain.tls?.subject || "—"}</p>
                  <p>Issuer {domain.tls?.issuer || domain.tls?.error || "—"}</p>
                  <p>Until {domain.tls?.not_after || "—"}</p>
                </div>
                <div>
                  <p className="font-mono text-zinc-600 uppercase text-[10px] mb-1">IPs</p>
                  {(domain.ip || []).map((row) => (
                    <p key={row.ip}>
                      {row.ip} · {row.org || row.isp || "—"} · {row.country || "—"}
                      {row.ports?.length ? ` · ports ${row.ports.slice(0, 8).join(",")}` : ""}
                    </p>
                  ))}
                </div>
              </div>
              {domain.certificates?.length > 0 && (
                <p className="text-[11px] text-zinc-500">
                  Cert names: {domain.certificates.slice(0, 12).join(", ")}
                </p>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                {domain.links &&
                  Object.entries(domain.links).map(([name, href]) => (
                    <a
                      key={name}
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="h-7 px-2 rounded-md border border-zinc-800 text-[10px] font-mono uppercase text-zinc-300 hover:text-matrix hover:border-matrix/40 inline-flex items-center gap-1"
                    >
                      {name} <ExternalLink className="h-3 w-3" />
                    </a>
                  ))}
              </div>
            </section>
          )}

          <section className="flex flex-wrap gap-2">
            {data.reports?.map((item) => (
              <a
                key={item.name}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="h-7 px-2 rounded-md bg-zinc-900 border border-zinc-800 text-[10px] font-mono text-zinc-300 hover:text-matrix"
              >
                Report via {item.name}
              </a>
            ))}
          </section>
        </div>
      )}
    </div>
  );
}
