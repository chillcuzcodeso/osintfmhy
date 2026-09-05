import { useRef, useState } from "react";
import { Phone } from "lucide-react";
import { lookupPhone } from "../lib/api.js";
import { Card, Field, LookupForm, LookupHeader, Pill } from "../components/LookupKit.jsx";

export default function PhoneCard({ seed = "" }) {
  const [q, setQ] = useState(seed.trim());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const last = useRef("");

  async function run(value = q) {
    const target = value.trim();
    if (target.length < 3 || last.current === target) return;
    last.current = target;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupPhone(target));
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
          icon={Phone}
          kicker="Phone Card"
          title="Numbering-plan card"
          blurb="Country, area, timezone, original carrier, and line type from the public numbering plan. Not the person who owns the phone."
        />
        <LookupForm
          value={q}
          onChange={(value) => {
            setQ(value);
            if ((value.match(/\d/g) || []).length >= 10) run(value);
          }}
          onSubmit={(e) => {
            e.preventDefault();
            last.current = "";
            run();
          }}
          loading={loading}
          placeholder="+61 412 345 678"
          label="Phone number"
          icon={Phone}
        />
      </div>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {data && (
        <Card className="max-w-xl">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[13px] font-mono text-matrix">{data.international || data.e164}</h3>
            <Pill ok={data.valid} label={data.valid ? "valid" : "not valid"} />
          </div>
          <Field label="e164" value={data.e164} />
          <Field label="country" value={data.country} />
          <Field label="region" value={data.region} />
          <Field label="type" value={data.line_type} />
          <Field label="carrier" value={data.carrier || "unknown / MVNO"} />
          <Field label="timezones" value={data.timezones} />
          <p className="text-[10px] text-zinc-600 pt-1">{data.note}</p>
        </Card>
      )}
    </div>
  );
}
