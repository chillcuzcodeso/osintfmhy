import {
  UserSearch,
  Globe,
  Server,
  Image,
  Mail,
  Archive,
  MapPin,
  Share2,
  ExternalLink,
} from "lucide-react";

const BENCH = [
  {
    group: "Identity",
    icon: UserSearch,
    tools: [
      { name: "WhatsMyName", desc: "Username occupancy across platforms", url: "https://whatsmyname.app/" },
      { name: "Namechk", desc: "Handle availability sweep", url: "https://namechk.com/" },
      { name: "IDCrawl", desc: "People / username index", url: "https://www.idcrawl.com/" },
    ],
  },
  {
    group: "Domain / DNS",
    icon: Globe,
    tools: [
      { name: "crt.sh", desc: "Certificate transparency", url: "https://crt.sh/", q: (q) => `https://crt.sh/?q=${encodeURIComponent(q)}` },
      { name: "SecurityTrails", desc: "Historical DNS / WHOIS", url: "https://securitytrails.com/" },
      { name: "DNSdumpster", desc: "Passive recon map", url: "https://dnsdumpster.com/" },
      { name: "ViewDNS", desc: "WHOIS, reverse IP, records", url: "https://viewdns.info/" },
    ],
  },
  {
    group: "Host / IP",
    icon: Server,
    tools: [
      { name: "IPinfo", desc: "ASN, geo, anycast", url: "https://ipinfo.io/", q: (q) => `https://ipinfo.io/${encodeURIComponent(q)}` },
      { name: "Shodan", desc: "Internet-facing service index", url: "https://www.shodan.io/", q: (q) => `https://www.shodan.io/search?query=${encodeURIComponent(q)}` },
      { name: "AbuseIPDB", desc: "Reported abuse reputation", url: "https://www.abuseipdb.com/" },
      { name: "Censys", desc: "Host and cert search", url: "https://search.censys.io/" },
    ],
  },
  {
    group: "Imagery",
    icon: Image,
    tools: [
      { name: "TinEye", desc: "Reverse image search", url: "https://tineye.com/" },
      { name: "Yandex Images", desc: "Visual match engine", url: "https://yandex.com/images/" },
      { name: "Google Images", desc: "Camera / web visual search", url: "https://images.google.com/" },
    ],
  },
  {
    group: "Communications",
    icon: Mail,
    tools: [
      { name: "Epieos", desc: "Email / phone footprint", url: "https://epieos.com/" },
      { name: "Hunter", desc: "Domain mailbox patterns", url: "https://hunter.io/" },
      { name: "Have I Been Pwned", desc: "Breach exposure check", url: "https://haveibeenpwned.com/" },
    ],
  },
  {
    group: "Archives",
    icon: Archive,
    tools: [
      { name: "Wayback Machine", desc: "Historical snapshots", url: "https://web.archive.org/", q: (q) => `https://web.archive.org/web/*/${encodeURIComponent(q)}` },
      { name: "archive.today", desc: "On-demand page capture", url: "https://archive.today/" },
      { name: "GhostArchive", desc: "Social media snapshots", url: "https://ghostarchive.org/" },
    ],
  },
  {
    group: "Geo",
    icon: MapPin,
    tools: [
      { name: "Google Earth", desc: "Imagery / terrain", url: "https://earth.google.com/web/" },
      { name: "Overpass Turbo", desc: "OpenStreetMap query", url: "https://overpass-turbo.eu/" },
      { name: "OpenStreetMap", desc: "Collaborative basemap", url: "https://www.openstreetmap.org/" },
    ],
  },
  {
    group: "Social graph",
    icon: Share2,
    tools: [
      { name: "Reddit Search", desc: "Thread / user lookup", url: "https://www.reddit.com/search/" },
      { name: "IntelTechniques", desc: "OSINT search forms", url: "https://inteltechniques.com/tools/" },
      { name: "OSINT Framework", desc: "Discipline index", url: "https://osintframework.com/" },
    ],
  },
];

export default function ActiveOsintTools({ query }) {
  const seed = query.trim();

  return (
    <div className="h-full overflow-y-auto p-3 space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-matrix">Active bench</p>
          <h2 className="text-sm font-medium text-zinc-100">Public OSINT launchers</h2>
        </div>
        <p className="text-[10px] font-mono text-zinc-500">
          {seed ? `SEED // ${seed}` : "Optional: type a target in global search, then launch"}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-2.5">
        {BENCH.map((group) => {
          const Icon = group.icon;
          return (
            <section
              key={group.group}
              className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2.5"
            >
              <header className="flex items-center gap-2 mb-2 px-0.5">
                <Icon className="h-3.5 w-3.5 text-emerald-400" />
                <h3 className="text-[11px] font-mono uppercase tracking-wider text-zinc-300">
                  {group.group}
                </h3>
              </header>
              <ul className="space-y-1">
                {group.tools.map((tool) => {
                  const href = seed && tool.q ? tool.q(seed) : tool.url;
                  return (
                    <li key={tool.name}>
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-matrix/5 group"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block text-[12px] text-zinc-100 group-hover:text-matrix truncate">
                            {tool.name}
                          </span>
                          <span className="block text-[10px] text-zinc-500 truncate">{tool.desc}</span>
                        </span>
                        <ExternalLink className="h-3 w-3 text-zinc-600 group-hover:text-matrix shrink-0" />
                      </a>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
