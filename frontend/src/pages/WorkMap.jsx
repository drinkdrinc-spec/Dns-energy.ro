import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, FolderOpen, MapPin, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Layout";

const LEAFLET_VERSION = "1.9.4";
const MAP_CENTER = [46.1, 25.1];
const STATUS_COLORS = {
  "de depus": "#e58b19", "de depunere": "#e58b19", "în lucru": "#e58b19", "dosar în pregătire": "#e58b19",
  "depus": "#3478e5", "depus la operatorul de distribuție": "#3478e5", "depusă": "#3478e5", "generată": "#3478e5", "generata": "#3478e5",
  "atr": "#8745c7", "atr emis": "#8745c7", "aviz tehnic emis": "#8745c7",
  "instalat": "#159b8a", "montaj efectuat": "#159b8a", "programat pentru montaj": "#159b8a",
  "finalizat": "#166b45", "prosumator activ": "#166b45", "probe și punere în funcțiune": "#166b45",
};
const LEGEND = [["De depus", "#e58b19"], ["Depus", "#3478e5"], ["ATR", "#8745c7"], ["Instalat", "#159b8a"], ["Finalizat", "#166b45"]];
let leafletPromise;

function leaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;
    css.crossOrigin = "";
    document.head.appendChild(css);
    const script = document.createElement("script");
    script.src = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;
    script.crossOrigin = "";
    script.onload = () => resolve(window.L);
    script.onerror = () => { leafletPromise = null; reject(new Error("Biblioteca hărții nu s-a încărcat.")); };
    document.head.appendChild(script);
  });
  return leafletPromise;
}

function locationOf(item) {
  return [item.locality, item.county].filter((part) => String(part || "").trim()).join(", ");
}

function colorFor(stage) {
  const value = String(stage || "").trim().toLocaleLowerCase("ro-RO");
  if (STATUS_COLORS[value]) return STATUS_COLORS[value];
  if (value.includes("finalizat") || value.includes("activ")) return "#166b45";
  if (value.includes("instalat") || value.includes("montaj") || value.includes("punere în funcțiune")) return "#159b8a";
  if (value.includes("atr") || value.includes("aviz")) return "#8745c7";
  if (value.includes("depus") || value.includes("generat")) return "#3478e5";
  if (value.includes("pregăt") || value.includes("lucru") || value.includes("depus")) return "#e58b19";
  return "#64748b";
}

function safeText(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

async function geocode(place) {
  const cacheKey = `dns-map-geocode:${place.toLocaleLowerCase("ro-RO")}`;
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
    if (Array.isArray(cached) && cached.length === 2 && cached.every(Number.isFinite)) return cached;
  } catch { /* Ignore malformed cache entries. */ }
  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("format", "jsonv2");
  url.searchParams.set("limit", "1");
  url.searchParams.set("countrycodes", "ro");
  url.searchParams.set("q", `${place}, România`);
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Serviciul de localizare nu este disponibil.");
  const results = await response.json();
  if (!results[0]) return null;
  const point = [Number(results[0].lat), Number(results[0].lon)];
  if (!point.every(Number.isFinite)) return null;
  try { localStorage.setItem(cacheKey, JSON.stringify(point)); } catch { /* The map remains usable if storage is full. */ }
  return point;
}

export default function WorkMap() {
  const [rows, setRows] = useState([]);
  const [missingLocationCount, setMissingLocationCount] = useState(0);
  const [stage, setStage] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [mapLoading, setMapLoading] = useState(false);
  const [error, setError] = useState("");
  const [mapError, setMapError] = useState("");
  const [unmappedCount, setUnmappedCount] = useState(0);
  const mapElement = useRef(null);
  const mapInstance = useRef(null);
  const markerLayer = useRef(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/work-map", { params: { include_archived: includeArchived } });
      const allRows = (Array.isArray(response.data) ? response.data : []).map((item) => ({
        ...item,
        moduleLabel: item.module_label,
        href: ({ prosumator: "/prosumator", atr: "/cerere-atr", power: "/spor-putere", diu: "/diu" })[item.module],
      }));
      setMissingLocationCount(allRows.filter((row) => !row.locality && !row.county).length);
      setRows(allRows.filter((row) => row.locality || row.county));
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "Nu am putut încărca lucrările. Încearcă din nou.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [includeArchived]);

  const stages = useMemo(() => [...new Set(rows.map((row) => row.stage).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ro-RO")), [rows]);
  const visible = useMemo(() => rows.filter((row) => !stage || row.stage === stage), [rows, stage]);
  const groups = useMemo(() => {
    const grouped = new Map();
    visible.forEach((row) => {
      const place = locationOf(row) || "Locație necompletată";
      const key = place.toLocaleLowerCase("ro-RO");
      const group = grouped.get(key) || { place, items: [] };
      group.items.push(row);
      grouped.set(key, group);
    });
    return [...grouped.values()].sort((a, b) => b.items.length - a.items.length || a.place.localeCompare(b.place, "ro-RO"));
  }, [visible]);

  useEffect(() => {
    let cancelled = false;
    let map;
    let markers;
    const render = async () => {
      if (!mapElement.current || loading) return;
      setMapLoading(true);
      setMapError("");
      try {
        const L = await leaflet();
        if (cancelled || !mapElement.current) return;
        if (!mapInstance.current) {
          mapInstance.current = L.map(mapElement.current, { scrollWheelZoom: false, preferCanvas: true }).setView(MAP_CENTER, 6);
          L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 18,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> · localități: <a href="https://www.openstreetmap.org/about" target="_blank" rel="noreferrer">Nominatim</a>',
          }).addTo(mapInstance.current);
        }
        map = mapInstance.current;
        markers = markerLayer.current || L.layerGroup().addTo(map);
        markerLayer.current = markers;
        markers.clearLayers();
        const locations = groups.slice(0, 50);
        let unmapped = Math.max(0, groups.length - locations.length);
        const bounds = [];
        for (let index = 0; index < locations.length; index += 1) {
          if (cancelled) return;
          const group = locations[index];
          let point = null;
          try { point = await geocode(group.place); } catch { /* Keep the dossier in the list if map lookup fails. */ }
          if (cancelled) return;
          if (point) {
            bounds.push(point);
            const statuses = [...new Set(group.items.map((item) => item.stage))];
            const color = statuses.length === 1 ? colorFor(statuses[0]) : "#177955";
            const isCluster = group.items.length > 1;
            const icon = L.divIcon({ className: "dns-map-marker-wrap", html: `<span class="dns-map-marker${isCluster ? " dns-map-marker--cluster" : ""}" style="--marker-color:${color}">${isCluster ? group.items.length : ""}</span>`, iconSize: [isCluster ? 38 : 18, isCluster ? 38 : 18], iconAnchor: [19, 19] });
            const marker = L.marker(point, { icon }).addTo(markers);
            const entries = group.items.map((item) => `<li><b>${safeText(item.number || item.moduleLabel)}</b><br><span>${safeText(item.moduleLabel)} · ${safeText(item.stage || "În lucru")}${item.operator ? ` · ${safeText(item.operator)}` : ""}</span><br><a href="${safeText(item.href)}?edit=${encodeURIComponent(item.id)}">Deschide dosarul</a></li>`).join("");
            marker.bindPopup(`<strong>${safeText(group.place)}</strong><ul class="dns-map-popup-list">${entries}</ul>`, { maxWidth: 330 });
            if (group.items.length > 1) marker.on("click", () => { if (map.getZoom() < 11) map.setView(point, 11); });
          } else unmapped += 1;
          // Nominatim asks clients to stay at or below one request per second.
          if (index < locations.length - 1) await new Promise((resolve) => setTimeout(resolve, 1050));
        }
        if (cancelled) return;
        setUnmappedCount(unmapped);
        if (bounds.length > 1) map.fitBounds(bounds, { padding: [28, 28], maxZoom: 10 });
        else if (bounds.length === 1) map.setView(bounds[0], 9);
        else map.setView(MAP_CENTER, 6);
        window.setTimeout(() => map.invalidateSize(), 100);
      } catch (mapLoadError) {
        if (!cancelled) setMapError(mapLoadError.message || "Harta nu s-a putut încărca.");
      } finally {
        if (!cancelled) setMapLoading(false);
      }
    };
    render();
    return () => { cancelled = true; };
  }, [groups, loading]);

  return <>
    <PageHeader eyebrow="Lucrări" title="Harta lucrărilor" sub="Lucrările sunt grupate după localitate. Selectează un marker pentru stadiu și deschiderea dosarului." action={<button type="button" onClick={load} disabled={loading} className="den-btn-secondary inline-flex min-h-10 items-center gap-2 px-3 text-sm"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Reîncarcă</button>} />

    <section className="den-panel mb-4 flex flex-wrap items-center justify-between gap-3" aria-label="Filtre hartă">
      <label className="den-field min-w-[220px] flex-1"><span>Filtrează după etapă</span><select className="den-input" value={stage} onChange={(event) => setStage(event.target.value)}><option value="">Toate etapele</option>{stages.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label className="inline-flex min-h-10 items-center gap-2 pt-4 text-sm"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include dosarele arhivate</label>
      <div className="text-xs" style={{ color: "var(--muted)" }}>{loading ? "Se încarcă…" : `${visible.length} lucrări pe hartă · ${groups.length} localități`}{missingLocationCount ? ` · ${missingLocationCount} fără localitate/județ` : ""}{mapLoading ? " · Se poziționează…" : ""}{unmappedCount ? ` · ${unmappedCount} fără coordonate` : ""}</div>
    </section>

    {error && <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {mapError && <div role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{mapError} Lista lucrărilor rămâne disponibilă mai jos.</div>}
    <section className="den-panel mb-4 overflow-hidden p-0" aria-label="Hartă interactivă a lucrărilor">
      <div ref={mapElement} className="dns-work-map" data-testid="work-map" role="application" aria-label="Hartă interactivă OpenStreetMap cu lucrări DNS Energy" />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t px-3 py-2.5 text-xs" style={{ borderColor: "var(--line)" }} aria-label="Legendă stadii">
        {LEGEND.map(([label, color]) => <span key={label} className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />{label}</span>)}
        <span className="ml-auto text-[10px]" style={{ color: "var(--muted)" }}>Poziționarea folosește numai localitatea și județul. Nu se transmit nume, adresă exactă sau POD.</span>
      </div>
    </section>

    {loading ? <div className="den-panel text-sm" role="status">Se încarcă lucrările…</div> : groups.length === 0 ? <div className="den-panel text-sm" data-testid="work-map-empty">Nu există lucrări cu județ și localitate completate pentru filtrul ales.</div> :
      <div className="grid gap-3 lg:grid-cols-2" data-testid="work-map-groups">
        {groups.map((group) => <section key={group.place} className="den-panel" data-testid="work-map-place">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-base font-bold"><MapPin size={17} style={{ color: "var(--blue)" }} />{group.place}</h2>
            <a href={`https://www.openstreetmap.org/search?query=${encodeURIComponent(`${group.place}, România`)}`} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-9 items-center gap-1 rounded-lg border px-2.5 text-xs font-semibold" style={{ borderColor: "var(--line)" }} aria-label={`Deschide harta pentru ${group.place}`}>Deschide harta <ExternalLink size={13} /></a>
          </div>
          <div className="mb-3 flex flex-wrap gap-1.5">{[...new Set(group.items.map((item) => item.stage))].map((item) => <span key={item} className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ background: `${colorFor(item)}1a`, color: colorFor(item) }}>{item} · {group.items.filter((row) => row.stage === item).length}</span>)}</div>
          <ul className="divide-y" style={{ borderColor: "var(--line)" }}>{group.items.map((item) => <li key={`${item.module}-${item.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2.5 first:pt-0 last:pb-0">
            <div className="min-w-0"><div className="truncate text-sm font-semibold">{item.number || item.moduleLabel}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{item.moduleLabel}{item.operator ? ` · ${item.operator}` : ""}{item.archived ? " · Arhivat" : ""}</div></div>
            <Link to={`${item.href}?edit=${encodeURIComponent(item.id)}`} className="inline-flex min-h-9 items-center gap-1 rounded-lg border px-2.5 text-xs font-semibold" style={{ borderColor: "var(--line)" }}><FolderOpen size={13} /> Deschide dosarul</Link>
          </li>)}</ul>
        </section>)}
      </div>}
  </>;
}

