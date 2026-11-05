import { useEffect, useRef, useState } from "react";
import { api, downloadAuthenticatedFile } from "@/lib/api";

const MARKERS = ["Stâlp", "BMP", "TEG", "CEF", "BESS", "Contor"];
const W = 1000;
const H = 620;
const clamp = (value, max) => Math.max(0, Math.min(max, value));
const uid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function AtrSitePlan({ id, value, files = [], onChange }) {
  const svgRef = useRef(null);
  const backgroundUrlRef = useRef("");
  const [tool, setTool] = useState("marker:CEF");
  const [dragging, setDragging] = useState("");
  const [backgroundUrl, setBackgroundUrl] = useState("");
  const [backgroundError, setBackgroundError] = useState("");
  const plan = value && typeof value === "object" ? value : {};
  const markers = Array.isArray(plan.markers) ? plan.markers : [];
  const boundary = Array.isArray(plan.boundary) ? plan.boundary : [];
  const route = Array.isArray(plan.route) ? plan.route : [];
  const imageFiles = files.filter((file) => {
    const type = String(file.content_type || "").toLowerCase();
    const name = String(file.original_filename || "").toLowerCase();
    return ["image/png", "image/jpeg", "image/webp", "application/pdf"].includes(type) || /\.(png|jpe?g|webp|pdf)$/.test(name);
  });
  const selectedBackground = String(plan.background_path || "");
  const selectedImage = imageFiles.find((file) => file.storage_path === selectedBackground);
  useEffect(() => {
    let active = true;
    const clearCurrent = () => {
      if (backgroundUrlRef.current) URL.revokeObjectURL(backgroundUrlRef.current);
      backgroundUrlRef.current = "";
      setBackgroundUrl("");
    };
    clearCurrent();
    setBackgroundError("");
    if (!selectedImage?.storage_path) {
      return () => { active = false; };
    }
    if (!id) {
      setBackgroundError("Salvează cererea ATR înainte de previzualizarea fundalului.");
      return () => { active = false; };
    }
    api.get(`/atr/${encodeURIComponent(id)}/site-plan-background`, { params: { path: selectedImage.storage_path }, responseType: "blob" })
      .then((response) => {
        const mime = String(response.headers["content-type"] || response.data?.type || "").split(";")[0].toLowerCase();
        if (!["image/png", "image/jpeg", "image/webp"].includes(mime)) throw new Error("Tipul de imagine nu este acceptat.");
        const url = URL.createObjectURL(response.data);
        if (!active) { URL.revokeObjectURL(url); return; }
        if (backgroundUrlRef.current) URL.revokeObjectURL(backgroundUrlRef.current);
        backgroundUrlRef.current = url;
        setBackgroundUrl(url);
        setBackgroundError("");
      })
      .catch(() => {
        if (!active) return;
        clearCurrent();
        setBackgroundError("Nu s-a putut previzualiza fișierul. Verifică atașamentul „Plan de situație” și încearcă din nou.");
      });
    return () => {
      active = false;
      if (backgroundUrlRef.current) URL.revokeObjectURL(backgroundUrlRef.current);
      backgroundUrlRef.current = "";
    };
  }, [id, selectedImage?.storage_path]);
  const hasGeometry = markers.length > 0 || boundary.length > 0 || route.length > 0;
  const point = (event) => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM?.();
    if (!svg || !matrix) return null;
    const cursor = svg.createSVGPoint();
    cursor.x = event.clientX;
    cursor.y = event.clientY;
    const local = cursor.matrixTransform(matrix.inverse());
    return { x: Math.round(clamp(local.x, W)), y: Math.round(clamp(local.y, H)) };
  };
  const change = (next) => onChange({ ...plan, ...next, version: 1 });
  const addPoint = (event) => {
    if (dragging) return;
    const p = point(event);
    if (!p) return;
    if (tool.startsWith("marker:")) {
      const type = tool.slice(7);
      change({ markers: [...markers, { id: uid(), type, label: type, ...p }] });
    } else if (tool === "boundary") change({ boundary: [...boundary, p] });
    else if (tool === "route") change({ route: [...route, p] });
  };
  const moveMarker = (event) => {
    if (!dragging) return;
    const p = point(event);
    if (p) change({ markers: markers.map((marker) => marker.id === dragging ? { ...marker, ...p } : marker) });
  };
  const polyline = (points, close = false) => points.map((p) => `${p.x},${p.y}`).join(" ") + (close && points.length > 2 ? ` ${points[0].x},${points[0].y}` : "");
  const activeLabel = tool.startsWith("marker:") ? `adaugă ${tool.slice(7)}` : tool === "boundary" ? "conturează limita proprietății" : tool === "route" ? "trasează ruta cablului" : "selectează un simbol";

  return <details className="mt-4 rounded-xl border p-3 sm:p-4" style={{ borderColor: "var(--line)" }} data-testid="atr-site-plan-editor">
    <summary className="cursor-pointer"><h3 className="text-sm font-bold">Plan de situație — schiță de amplasament</h3>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Plasează și mută simbolurile, traseul cablului și limita proprietății. Schița este ilustrativă, fără scară sau georeferențiere; atașează planul oficial vizat separat.</p></summary>
    <label className="mt-3 block max-w-xl text-xs font-semibold">Fundal din planul atașat
      <select className="den-input mt-1" value={selectedBackground} onChange={(event) => onChange({ ...plan, version: 1, background_path: event.target.value })} data-testid="atr-site-plan-background">
        <option value="">Fără fundal imagine</option>
        {imageFiles.map((file) => <option key={file.storage_path} value={file.storage_path}>{file.original_filename || "Plan imagine"}</option>)}
      </select>
    </label>
    {!imageFiles.length && <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Atașează o imagine PNG/JPEG/WebP sau un PDF în documentul „Plan de situație”. Pentru PDF se folosește prima pagină ca fundal; originalul rămâne în dosar.</p>}
    {selectedImage && !id && <p className="mt-1 text-xs text-amber-800">Salvează cererea ATR înainte să încarci fundalul în editor.</p>}
    {backgroundError && <p className="mt-1 text-xs text-amber-800" role="status" data-testid="atr-site-plan-background-error">{backgroundError}</p>}
    {id && <button type="button" disabled={!hasGeometry} className="mt-3 rounded-lg border px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/atr/${encodeURIComponent(id)}/site-plan.pdf`, "Schiță_amplasament_ATR.pdf")} data-testid="atr-site-plan-download">Descarcă PDF separat</button>}
    <div className="mt-3 flex flex-wrap gap-2" role="toolbar" aria-label="Instrumente pentru schiță">
      {MARKERS.map((type) => <button key={type} type="button" className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold" aria-pressed={tool === `marker:${type}`} style={{ borderColor: tool === `marker:${type}` ? "var(--blue)" : "var(--line)", color: tool === `marker:${type}` ? "var(--blue)" : "var(--ink)" }} onClick={() => setTool(`marker:${type}`)}>{type}</button>)}
      <button type="button" className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold" aria-pressed={tool === "route"} style={{ borderColor: tool === "route" ? "var(--blue)" : "var(--line)" }} onClick={() => setTool("route")}>Traseu cablu</button>
      <button type="button" className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold" aria-pressed={tool === "boundary"} style={{ borderColor: tool === "boundary" ? "var(--blue)" : "var(--line)" }} onClick={() => setTool("boundary")}>Limită proprietate</button>
      <button type="button" className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold" onClick={() => { setTool("select"); setDragging(""); }}>Încheie traseu / selectare</button>
      <button type="button" className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold" style={{ borderColor: "#fecaca", color: "#991b1b" }} onClick={() => change({ markers: [], route: [], boundary: [] })}>Șterge schița</button>
    </div>
    <p className="my-2 text-xs" style={{ color: "var(--muted)" }}>Instrument activ: {activeLabel}. Apasă pe plan pentru a adăuga puncte; trage simbolurile pentru repoziționare.</p>
    <p className="mb-2 text-xs" style={{ color: "var(--muted)" }}>Salvează dosarul ATR după editare, înainte de a descărca PDF-ul.</p>
    <div className="overflow-hidden rounded-lg border bg-white" style={{ borderColor: "var(--line)" }}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Schiță editabilă pentru amplasarea echipamentelor ATR" className="block w-full touch-none" style={{ minHeight: 260, cursor: tool === "select" ? "default" : "crosshair" }} onClick={addPoint} onPointerMove={moveMarker} onPointerUp={() => setDragging("")} onPointerCancel={() => setDragging("")}>
        <defs><pattern id="atr-plan-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="#e8edf3" strokeWidth="1" /></pattern></defs>
        <rect width={W} height={H} fill="url(#atr-plan-grid)" />
        {backgroundUrl && <image href={backgroundUrl} x="0" y="0" width={W} height={H} preserveAspectRatio="xMidYMid meet" opacity=".8" />}
        {boundary.length > 0 && <><polyline points={polyline(boundary, true)} fill={boundary.length > 2 ? "rgba(217,119,6,.08)" : "none"} stroke="#b45309" strokeWidth="4" strokeDasharray="12 8" />{boundary.map((p, i) => <circle key={`b${i}`} cx={p.x} cy={p.y} r="6" fill="#fff" stroke="#b45309" strokeWidth="3" />)}</>}
        {route.length > 0 && <><polyline points={polyline(route)} fill="none" stroke="#2563eb" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />{route.map((p, i) => <circle key={`r${i}`} cx={p.x} cy={p.y} r="5" fill="#fff" stroke="#2563eb" strokeWidth="3" />)}</>}
        {markers.map((marker) => <g key={marker.id} transform={`translate(${marker.x} ${marker.y})`} onClick={(event) => event.stopPropagation()} onPointerDown={(event) => { event.stopPropagation(); event.currentTarget.ownerSVGElement?.setPointerCapture?.(event.pointerId); setDragging(marker.id); setTool("select"); }}>
          <circle r="24" fill="#fff" stroke="#163c70" strokeWidth="4" />
          <text textAnchor="middle" y="6" fontSize="17" fontWeight="700" fill="#163c70">{marker.type.slice(0, 4)}</text>
          <text textAnchor="middle" y="42" fontSize="16" fontWeight="600" fill="#1f2937" paintOrder="stroke" stroke="white" strokeWidth="5">{marker.label || marker.type}</text>
          <title>{marker.type} — trage pentru mutare</title>
        </g>)}
        {!markers.length && !route.length && !boundary.length && <text x={W / 2} y={H / 2} textAnchor="middle" fill="#64748b" fontSize="24">Plan simplu — alege un simbol și plasează-l</text>}
      </svg>
    </div>
    {markers.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{markers.map((marker) => <label key={`label-${marker.id}`} className="flex items-center gap-2 text-xs"><span className="w-16 font-semibold">{marker.type}</span><input className="den-input" aria-label={`Etichetă ${marker.type}`} value={marker.label || ""} onChange={(event) => change({ markers: markers.map((item) => item.id === marker.id ? { ...item, label: event.target.value } : item) })} /><button type="button" aria-label={`Șterge ${marker.type}`} className="rounded border px-2 py-1" onClick={() => change({ markers: markers.filter((item) => item.id !== marker.id) })}>Șterge</button></label>)}</div>}
  </details>;
}

