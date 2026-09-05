export const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function readJson(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function fetchTools() {
  return fetch(apiUrl("/api/tools")).then(readJson);
}

export function searchCatalog(q, limit = 80) {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return fetch(apiUrl(`/api/search?${params}`)).then(readJson);
}

export function scanUsername(handle) {
  const params = new URLSearchParams({ handle });
  return fetch(apiUrl(`/api/osint/username?${params}`)).then(readJson);
}

export function openUsernameScanStream(handle, { onStart, onResult, onDone, onError }) {
  const params = new URLSearchParams({ handle, stream: "true" });
  const source = new EventSource(apiUrl(`/api/osint/username?${params}`));

  source.addEventListener("start", (event) => {
    onStart?.(JSON.parse(event.data));
  });
  source.addEventListener("result", (event) => {
    onResult?.(JSON.parse(event.data));
  });
  source.addEventListener("done", (event) => {
    onDone?.(JSON.parse(event.data));
    source.close();
  });
  source.onerror = () => {
    source.close();
    onError?.(new Error("Username scan stream closed unexpectedly"));
  };
  return () => source.close();
}

export function runTerminalCommand(target, command) {
  return fetch(apiUrl("/api/terminal/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, command }),
  }).then(readJson);
}

export function triggerScrape(fresh = false) {
  const qs = fresh ? "?fresh=true" : "";
  return fetch(apiUrl(`/api/scrape-update${qs}`), { method: "POST" }).then(async (res) => {
    if (res.status === 409) return readJson(res).catch(() => ({ running: true }));
    return readJson(res);
  });
}
