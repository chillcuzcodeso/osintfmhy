import { useEffect, useRef, useState } from "react";
import { ExternalLink, Globe } from "lucide-react";
import { lookupIp } from "../lib/api.js";
import { Card, Field, LookupForm, LookupHeader, Pill } from "../components/LookupKit.jsx";

function looksComplete(value) {
  const t = value.trim();
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(t)) return true;
  return t.includes(":") && /^[0-9a-fA-F:.]+$/.test(t) && t.length >= 4;
}

export default function IpLookup({ seed = "" }) {
  const [q, setQ] = useState(seed.trim());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const last = useRef("");

  async function run(value = q) {
    const target = value.trim();
    if (!target || last.current === target) return;
    last.current = target;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupIp(target));
    } catch (err) {
      setError(err.message);
      setData(null);
      last.current = "";
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (looksComplete(seed)) run(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onChange(value) {
    setQ(value);
    if (looksComplete(value)) run(value);
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <LookupHeader
          icon={Globe}
          kicker="IP Lookup"
          title="Where this address sits"
          blurb="City, region, ISP, ASN, reverse DNS, and a datacenter / proxy flag. City-level only — not a street address."
        />
        <LookupForm
          value={q}
          onChange={onChange}
          onSubmit={(e) => {
            e.preventDefault();
            last.current = "";
            run();
          }}
          loading={loading}
          placeholder="8.8.8.8 or 1.1.1.1"
          label="IP address"
          icon={Globe}
        />
      </div>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-2.5">
          <Card>
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-[13px] font-mono text-matrix break-all">{data.ip}</h3>
              <Pill
                ok={data.public}
                label={data.public ? data.scope || "public" : data.scope || "private"}
              />
            </div>
            <Field label="place" value={[data.city, data.region, data.country].filter(Boolean).join(", ")} />
            <Field label="coords" value={data.latitude != null ? `${data.latitude}, ${data.longitude}` : null} />
            <Field label="timezone" value={[data.timezone, data.utc_offset].filter(Boolean).join(" ")} />
            <Field label="isp" value={data.isp} />
            <Field label="org" value={data.org} />
            <Field label="asn" value={data.asn ? `AS${String(data.asn).replace(/^AS/i, "")}` : null} />
            <Field label="ptr" value={data.ptr || data.reverse_ipapi} />
            <Field label="hostnames" value={data.hostnames} />
            <Field label="ports" value={data.ports} />
            <div className="flex flex-wrap gap-1 pt-1">
              {data.hosting && <Pill ok={false} label="datacenter" />}
              {data.proxy && <Pill ok={false} label="proxy / vpn" />}
              {data.mobile && <Pill ok label="mobile" />}
            </div>
            <p className="text-[10px] text-zinc-600">{data.note}</p>
          </Card>
          {data.map?.embed && (
            <Card className="p-0 overflow-hidden">
              <iframe
                title="OpenStreetMap"
                src={data.map.embed}
                className="w-full h-64 border-0 bg-zinc-950"
              />
              <a
                href={data.map.osm}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-2 text-[10px] font-mono text-matrix"
              >
                Open map <ExternalLink className="h-3 w-3" />
              </a>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
