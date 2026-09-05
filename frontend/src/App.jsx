import { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import TopBar from "./components/TopBar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import IntelligenceDatabase from "./modules/IntelligenceDatabase.jsx";
import ActiveOsintTools from "./modules/ActiveOsintTools.jsx";
import TargetScanner from "./modules/TargetScanner.jsx";
import GamingScanner from "./modules/GamingScanner.jsx";
import ScamBrief from "./modules/ScamBrief.jsx";
import IpLookup from "./modules/IpLookup.jsx";
import PhoneCard from "./modules/PhoneCard.jsx";
import DiscordLookup from "./modules/DiscordLookup.jsx";
import WalletCard from "./modules/WalletCard.jsx";
import FileMeta from "./modules/FileMeta.jsx";
import TerminalDock from "./modules/TerminalDock.jsx";
import { fetchScrapeStatus, fetchTools, triggerScrape } from "./lib/api.js";

const EMPTY_CATALOG = { count: 0, category_count: 0, categories: [] };

export default function App() {
  const [module, setModule] = useState("database");
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [catalog, setCatalog] = useState(EMPTY_CATALOG);
  const [catalogError, setCatalogError] = useState(null);
  const [online, setOnline] = useState(false);
  const [searching, setSearching] = useState(false);
  const [hitCount, setHitCount] = useState(null);
  const [scrape, setScrape] = useState({ running: false });

  const loadCatalog = useCallback(async () => {
    try {
      const data = await fetchTools();
      setCatalog(data);
      setCatalogError(null);
      setOnline(true);
    } catch (err) {
      setCatalogError(err.message);
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
    fetchScrapeStatus()
      .then((status) => {
        if (status.running) setScrape({ running: true });
        if (status.error) setCatalogError(status.error);
      })
      .catch(() => {});
  }, [loadCatalog]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "/" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
        e.preventDefault();
        document.querySelector('input[aria-label="Global fuzzy search"]')?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleSearchState = useCallback((state) => {
    setSearching(Boolean(state.searching));
    setHitCount(state.resultCount);
    if (state.online === true) setOnline(true);
    if (state.online === false) setOnline(false);
  }, []);

  function handleQueryChange(value) {
    setQuery(value);
    if (value.trim()) setModule("database");
  }

  async function handleScrape(fresh) {
    try {
      setScrape({ running: true });
      await triggerScrape(fresh);
      const deadline = Date.now() + 180000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const status = await fetchScrapeStatus();
        setScrape({ running: Boolean(status.running), error: status.error });
        if (!status.running) {
          if (status.error) setCatalogError(status.error);
          break;
        }
      }
      await loadCatalog();
    } catch (err) {
      setCatalogError(err.message);
    } finally {
      setScrape({ running: false });
    }
  }

  const stats = useMemo(
    () => ({ tools: catalog.count || 0, categories: catalog.category_count || 0 }),
    [catalog],
  );

  return (
    <div className="h-full bg-slate-950 text-zinc-100 flex ops-grid">
      <Sidebar
        module={module}
        onChange={setModule}
        collapsed={collapsed}
        stats={stats}
      />
      <div className="flex-1 flex flex-col min-w-0 min-h-0 bg-slate-950/80">
        <TopBar
          query={query}
          onQueryChange={handleQueryChange}
          searching={searching}
          resultCount={hitCount}
          collapsed={collapsed}
          onToggleSidebar={() => setCollapsed((v) => !v)}
        />
        <main className="flex-1 min-h-0 bg-zinc-900/40">
          {module === "database" ? (
            <IntelligenceDatabase
              query={query}
              catalog={catalog}
              catalogError={catalogError}
              onRefresh={loadCatalog}
              onScrape={handleScrape}
              scraping={scrape.running}
              onSearchState={handleSearchState}
            />
          ) : module === "osint" ? (
            <ActiveOsintTools query={query} />
          ) : module === "scanner" ? (
            <TargetScanner seed={query} />
          ) : module === "gaming" ? (
            <GamingScanner seed={query} />
          ) : module === "scam" ? (
            <ScamBrief />
          ) : module === "ip" ? (
            <IpLookup seed={query} />
          ) : module === "phone" ? (
            <PhoneCard seed={query} />
          ) : module === "discord" ? (
            <DiscordLookup seed={query} />
          ) : module === "wallet" ? (
            <WalletCard seed={query} />
          ) : module === "exif" ? (
            <FileMeta />
          ) : (
            <TerminalDock seed={query} />
          )}
        </main>
        <StatusBar online={online} module={module} scrape={scrape} />
      </div>
    </div>
  );
}
