import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const field = (cfg, name) => (cfg.fields || []).find((f) => f.name === name);
const title = (f, fallback) => f?.label?.replace(/\s*\*$/, "") || fallback;
const selectStyle = { borderColor: "var(--line)" };

export function ProsumatorQuickForm({ cfg, form, setVal, refOptions }) {
  const [catalog, setCatalog] = useState([]);
  const [problem, setProblem] = useState("");
  useEffect(() => {
    api.get("/data/catalog").then((r) => setCatalog(Array.isArray(r.data) ? r.data : [])).catch(() => setProblem("Catalogul nu s-a putut încărca. Poți salva datele de bază și selecta echipamentele ulterior."));
  }, []);
  const clients = refOptions.clients || [];
  const clientField = field(cfg, "client_name");
  const selected = form.catalog_selection || {};
  const options = useMemo(() => ({
    inverter: catalog.filter((x) => x.category === "Invertor"),
    panel: catalog.filter((x) => x.category === "Panou"),
    battery: catalog.filter((x) => x.category === "Baterie"),
    meter: catalog.filter((x) => x.category === "Smart meter"),
  }), [catalog]);

  const choose = (kind, id) => {
    const item = options[kind].find((x) => x.id === id);
    const next = { ...selected, [kind]: id || "" };
    setVal("catalog_selection", next);
    if (kind === "inverter") {
      setVal("inverter", item?.brand_model || "");
      setVal("inverter_kw", item?.p_nom_kw || "");
      setVal("inverter_count", item ? (form.inverter_count || 1) : "");
      if (item) setVal("system_type", item.type === "Hibrid" ? "Hibrid cu baterie" : "On-grid");
    } else if (kind === "panel") {
      setVal("panels", item?.brand_model || "");
      setVal("panel_w", item?.w || "");
      setVal("panel_count", item ? (form.panel_count || 1) : "");
    } else if (kind === "battery") {
      setVal("battery", item?.brand_model || "");
      setVal("battery_kwh", item?.kwh || "");
      setVal("battery_v", item?.voltage || "");
      setVal("battery_ah", item?.ah || "");
      setVal("system_type", item ? "Hibrid cu baterie" : (options.inverter.find((x) => x.id === selected.inverter)?.type === "Hibrid" ? "Hibrid cu baterie" : "On-grid"));
      setVal("battery_coupling", item?.coupling || "");
      setVal("battery_count", item ? (form.battery_count || 1) : "");
    } else {
      setVal("smart_meter_present", item ? "Da" : "Nu");
      setVal("smart_meter_type", item?.brand_model || "");
    }
  };

  const input = (name, label, type = "text", opts) => (
    <label key={name} className="den-field">
      <span>{label}</span>
      {opts ? <select className="den-input" value={form[name] ?? ""} onChange={(e) => setVal(name, e.target.value)}><option value="">Alege...</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select>
        : <input className="den-input" type={type} step={type === "number" ? "any" : undefined} value={form[name] ?? ""} onChange={(e) => setVal(name, e.target.value)} />}
    </label>
  );
  const catalogSelect = (kind, label, category) => (
    <label key={kind} className="den-field">
      <span>{label}</span>
      <select className="den-input" style={selectStyle} value={selected[kind] || ""} onChange={(e) => choose(kind, e.target.value)}>
        <option value="">Alege din catalog...</option>
        {options[kind].map((x) => <option key={x.id} value={x.id}>{x.brand_model} {x.p_nom_kw ? `· ${x.p_nom_kw} kW` : x.w ? `· ${x.w} W` : x.kwh ? `· ${x.kwh} kWh` : ""}{!(x.datasheet && x.conformity) ? " · documente lipsă" : ""}</option>)}
      </select>
      {selected[kind] && (() => { const x = options[kind].find((v) => v.id === selected[kind]); return x && <small className="block mt-1" style={{ color: "var(--muted)" }}>Date preluate din catalog{x.datasheet && x.conformity ? " · fișă și conformitate disponibile" : " · verifică fișa tehnică și conformitatea"}</small>; })()}
    </label>
  );

  return <div className="space-y-5" data-testid="prosumator-quick-form">
    <section>
      <h3 className="text-sm font-bold mb-3">1. Client și loc de consum</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="den-field sm:col-span-2"><span>{title(clientField, "Beneficiar / client")} *</span>
          <select className="den-input" value={form.client_name || ""} onChange={(e) => {
            const v = e.target.value; setVal("client_name", v);
            const c = clients.find((x) => x.label === v);
            if (c) for (const k of ["cnp", "phone", "email", "address", "hq_address", "county", "pod", "operator", "cf_nr", "cadastral_nr"]) if (!form[k] && c[k]) setVal(k, c[k]);
          }}><option value="">Alege client...</option>{clients.map((c) => <option key={c.id} value={c.label}>{c.label}</option>)}</select>
        </label>
        {input("request_type", title(field(cfg, "request_type"), "Tip cerere"), "text", field(cfg, "request_type")?.options)}
        {input("operator", "Operator de distribuție", "text", field(cfg, "operator")?.options)}
        {input("address", "Adresa locului de consum")}
        {input("pod", "POD")}
        {input("power", "Putere evacuată cerută (kW)", "number")}
        {input("supply", title(field(cfg, "supply"), "Branșament"), "text", field(cfg, "supply")?.options)}
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Încarcă CI, factura și actul de proprietate cu butonul „Import din PDF (AI)”. Verifică datele extrase înainte de salvare.</p>
    </section>
    <section className="border-t pt-4" style={{ borderColor: "var(--line)" }}>
      <h3 className="text-sm font-bold mb-3">2. Echipamente</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        {catalogSelect("inverter", "Invertor", "Invertor")}
        {input("inverter_count", "Număr invertoare", "number")}
        {catalogSelect("panel", "Panou fotovoltaic", "Panou")}
        {input("panel_count", "Număr total panouri", "number")}
        {catalogSelect("battery", "Baterie (opțional)", "Baterie")}
        {input("battery_count", "Număr baterii", "number")}
        {catalogSelect("meter", "Smart meter (opțional)", "Smart meter")}
        <label className="den-field"><span>Backup</span><span className="flex items-center gap-2 min-h-10"><input type="checkbox" checked={form.backup === true || form.backup === "Da"} onChange={(e) => { setVal("backup", e.target.checked); setVal("anti_relay_present", e.target.checked ? "DA" : "NU"); }} /> Instalația include ieșire backup</span></label>
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Puterea și specificațiile se preiau din catalog. Dimensionările generate sunt propuneri tehnice și trebuie validate pe fișele producătorilor și de proiectant.</p>
      {problem && <p className="text-xs mt-2 text-amber-700">{problem}</p>}
      {catalog.length === 0 && !problem && <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Catalog gol. Adaugă modelele și fișele lor în Catalog echipamente.</p>}
    </section>
  </div>;
}
