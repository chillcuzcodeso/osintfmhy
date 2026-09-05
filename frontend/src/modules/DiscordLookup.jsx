import { useRef, useState } from "react";
import { ExternalLink, Hash } from "lucide-react";
import { lookupDiscord } from "../lib/api.js";
import { Card, Field, LookupForm, LookupHeader, Pill, unixMs } from "../components/LookupKit.jsx";

export default function DiscordLookup({ seed = "" }) {
  const [q, setQ] = useState(seed.trim());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const last = useRef("");

  async function run(value = q) {
    const target = value.trim();
    if (target.length < 2 || last.current === target) return;
    last.current = target;
    setLoading(true);
    setError(null);
    try {
      setData(await lookupDiscord(target));
    } catch (err) {
      setError(err.message);
      setData(null);
      last.current = "";
    } finally {
      setLoading(false);
    }
  }

  const invite = data?.invite;

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <LookupHeader
          icon={Hash}
          kicker="Discord / Snowflake"
          title="Invite preview and created-time"
          blurb="Public invite metadata plus snowflake timestamps. A Discord ID only encodes when it was minted — not the username."
        />
        <LookupForm
          value={q}
          onChange={(value) => {
            setQ(value);
            if (/discord\.gg\//i.test(value) || /^\d{17,20}$/.test(value.trim())) run(value);
          }}
          onSubmit={(e) => {
            e.preventDefault();
            last.current = "";
            run();
          }}
          loading={loading}
          placeholder="discord.gg/code or 17–20 digit ID"
          label="Discord invite or snowflake"
          icon={Hash}
        />
      </div>

      {error && <p className="text-[12px] font-mono text-rose-400">{error}</p>}

      {invite && (
        <Card>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[13px] text-zinc-100">{invite.guild || invite.code}</h3>
            <Pill ok={invite.found} label={invite.found ? "invite live" : "dead / missing"} />
          </div>
          {invite.error && <p className="text-[12px] text-rose-400">{invite.error}</p>}
          <Field label="code" value={invite.code} />
          <Field label="members" value={invite.members} />
          <Field label="online" value={invite.online} />
          <Field label="channel" value={invite.channel} />
          <Field label="inviter" value={invite.inviter} />
          <Field label="expires" value={invite.expires_at} />
          <Field label="nsfw" value={invite.found ? (invite.nsfw ? "yes" : "no") : null} />
          {invite.url && (
            <a
              href={invite.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] font-mono text-matrix"
            >
              Open invite <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </Card>
      )}

      {data?.snowflakes?.length > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {data.snowflakes.map((row) => (
            <Card key={`${row.id}-${row.role || "id"}`}>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-[12px] font-mono text-matrix break-all">{row.id}</h3>
                <Pill ok={row.plausible} label={row.role || (row.plausible ? "snowflake" : "unlikely")} />
              </div>
              <Field label="created" value={unixMs(row.created_unix_ms)} />
              <Field label="could be" value={row.could_be} />
              <p className="text-[10px] text-zinc-600">{row.note}</p>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
