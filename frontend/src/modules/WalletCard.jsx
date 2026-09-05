import { useRef, useState } from "react";
import { ExternalLink, Wallet } from "lucide-react";
import { lookupWallet } from "../lib/api.js";
import { Card, Field, LookupForm, LookupHeader, Pill, unixMs } from "../components/LookupKit.jsx";

const LOOKS_WALLET = /\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,}|0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33}\b/;

export default function WalletCard({ seed = "" }) {
  const [q, setQ] = useState(seed.trim());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const last = useRef("");

  async function run(value = q) {
    const target = value.trim();
    if (target.length < 8 || last.current === target) return;
    last.current = target;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupWallet(target));
    } catch (err) {
      setError(err.message);
      setData(null);
      last.current = "";
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <LookupHeader
          icon={Wallet}
          kicker="Wallet Card"
          title="Public chain snapshot"
          blurb="BTC, ETH, or TRON address → balance, tx count, and explorer. Public ledger data only."
        />
        <LookupForm
          value={q}
          onChange={(value) => {
            setQ(value);
            if (LOOKS_WALLET.test(value)) run(value);
          }}
          onSubmit={(e) => {
            e.preventDefault();
            last.current = "";
            run();
          }}
          loading={loading}
          placeholder="bc1…  0x…  or T…"
          label="Wallet address"
          icon={Wallet}
        />
      </div>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <Card className="max-w-xl">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[12px] font-mono uppercase text-zinc-100">{data.chain}</h3>
            <Pill ok={data.found} label={data.found ? "on chain" : "no record"} />
          </div>
          <Field label="address" value={data.address} />
          <Field
            label="balance"
            value={data.found && data.balance != null ? `${data.balance} ${data.unit}` : null}
          />
          <Field label="received" value={data.received != null ? `${data.received} ${data.unit}` : null} />
          <Field label="sent" value={data.sent != null ? `${data.sent} ${data.unit}` : null} />
          <Field label="txs" value={data.tx_count} />
          <Field label="ens" value={data.ens} />
          <Field label="contract" value={data.is_contract == null ? null : data.is_contract ? "yes" : "no"} />
          <Field label="created" value={unixMs(data.created_unix_ms)} />
          <Field label="last active" value={unixMs(data.last_active_unix_ms)} />
          <Field label="latest tx" value={data.latest_tx?.txid} />
          {data.error && <p className="text-[12px] text-rose-400">{data.error}</p>}
          {data.explorer && (
            <a
              href={data.explorer}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix"
            >
              Explorer <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </Card>
      )}
    </div>
  );
}
