import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const field = (cfg, name) => (cfg.fields || []).find((f) => f.name === name);
const title = (f, fallback) => f?.label?.replace(/\s*\*$/, "") || fallback;
const selectStyle = { borderColor: "var(--line)" };

export function ProsumatorQuickForm({ cfg, form, setVal, refOptions }) {
  const [catalog, setCatalog] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [problem, setProblem] = useState("");
  const [catalogSearch, setCatalogSearch] = useState({});
  useEffect(() => {
    api.get("/data/catalog").then((r) => setCatalog(Array.isArray(r.data) ? r.data : [])).catch(() => setProblem("Catalogul nu s-a putut încărca. Poți salva datele de bază și selecta echipamentele ulterior.")).finally(() => setCatalogLoading(false));
  }, []);
  const clients = (refOptions.clients || []).filter((client) => !/\\bTEST\\b/i.test(String(client.label || client.name || "")));
  const selected = form.catalog_selection || {};
  useEffect(() => {
    const inferred = { ...selected };
    for (const [kind, value] of [["inverter", form.inverter], ["panel", form.panels], ["battery", form.battery], ["meter", form.smart_meter_type]]) {
      if (inferred[kind] || !value) continue;
      const hit = options[kind].find((x) => x.brand_model === value);
      if (hit) inferred[kind] = hit.id;
    }
    if (JSON.stringify(inferred) !== JSON.stringify(selected)) setVal("catalog_selection", inferred);
  }, [catalog.length, form.inverter, form.panels, form.battery, form.smart_meter_type]);
  const options = useMemo(() => {
    const unique = (category) => {
      const seen = new Set();
      return catalog.filter((item) => {
        if (item.category !== category || /\bTEST\b/i.test(String(item.brand_model || ""))) return false;
        const key = String(item.brand_model || "").trim().toLocaleLowerCase("ro-RO");
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    };
    return {
      inverter: unique("Invertor"),
      panel: unique("Panou"),
      battery: unique("Baterie"),
      meter: unique("Smart meter"),
    };
  }, [catalog]);

  const cefUpdate = (kind, item, id) => {
    const cef = form.cef || { grid: {}, inverters: [], shared_batteries: [] };
    const old = cef.inverters?.[0] || { id: "main", strings: [], ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "H1Z2Z2-K" }, battery_mode: "none" };
    const inv = { ...old };
    if (kind === "inverter") Object.assign(inv, item ? {
      catalog_id: item.id, brand_model: item.brand_model, type: item.type, phases: item.phases, p_nom_kw: item.p_nom_kw, p_max_kw: item.p_max_kw,
      vdc_max: item.vdc_max, mppt_min: item.mppt_min, mppt_max: item.mppt_max, mppt_count: item.mppt_count, imax_mppt: item.imax_mppt,
      red_limit_mode: item.red_limit_mode || "Nu este declarată", count: Math.max(1, Number(form.inverter_count) || 1),
    } : { catalog_id: "", brand_model: "", p_nom_kw: "", p_max_kw: "", type: "", phases: "", count: 1 });
    if (kind === "panel") Object.assign(inv, item ? {
      panel_catalog_id: item.id, panel_model: item.brand_model, panel_w: item.w, panel_voc: item.voc, panel_vmp: item.vmp,
      panel_isc: item.isc, panel_coef_voc: item.coef_voc, panel_coef_vmp: item.coef_vmp,
    } : { panel_catalog_id: "", panel_model: "", panel_w: "", panel_voc: "", panel_vmp: "", panel_isc: "", panel_coef_voc: "", panel_coef_vmp: "" });
    if (kind === "battery") Object.assign(inv, item ? {
      battery_mode: "own", battery: { ...(inv.battery || {}), catalog_id: item.id, model: item.brand_model, kwh: item.kwh, ah: item.ah, voltage: item.voltage, coupling: item.coupling || "DC", modules: Number(form.battery_count || 1) },
    } : { battery_mode: "none", battery: {} });
    if (kind === "meter") setVal("cef", { ...cef, grid: { ...(cef.grid || {}), meter: item?.brand_model || "", meter_catalog_id: item?.id || "" } });
    else setVal("cef", { ...cef, grid: { ...(cef.grid || {}), ...(form.supply ? { supply: form.supply } : {}), ...(form.bransament_kw ? { bransament_kw: Number(form.bransament_kw) } : {}) }, inverters: [inv, ...(cef.inverters || []).slice(1)] });
    if (id === "") setVal("catalog_selection", { ...selected, [kind]: "" });
  };

  const choose = (kind, id) => {
    const item = options[kind].find((x) => x.id === id);
    setVal("catalog_selection", { ...selected, [kind]: id || "" });
    if (kind === "inverter") {
      setVal("inverter", item?.brand_model || ""); setVal("inverter_kw", item?.p_nom_kw || "");
      setVal("inverter_count", item ? (form.inverter_count || 1) : "");
      if (item) setVal("system_type", item.type === "Hibrid" ? "Hibrid cu baterie" : "On-grid");
    } else if (kind === "panel") {
      setVal("panels", item?.brand_model || ""); setVal("panel_w", item?.w || "");
      setVal("panel_count", item ? (form.panel_count || 1) : "");
    } else if (kind === "battery") {
      setVal("battery", item?.brand_model || ""); setVal("battery_kwh", item?.kwh || "");
      setVal("battery_v", item?.voltage || ""); setVal("battery_ah", item?.ah || "");
      setVal("battery_coupling", item?.coupling || ""); setVal("battery_count", item ? (form.battery_count || 1) : "");
      setVal("system_type", item ? "Hibrid cu baterie" : "On-grid");
    } else setVal("smart_meter_type", item?.brand_model || "");
    cefUpdate(kind, item, id);
  };

  const input = (name, label, type = "text", opts) => (
    <label key={name} className="den-field">
      <span>{label}</span>
      {opts ? <select className="den-input" value={form[name] ?? ""} onChange={(e) => { const v = e.target.value; setVal(name, v); if (name === "supply") setVal("cef", { ...(form.cef || {}), grid: { ...(form.cef?.grid || {}), supply: v } }); }}><option value="">Alege...</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select>
        : <input className="den-input" type={type} step={type === "number" ? "any" : undefined} value={form[name] ?? ""} onChange={(e) => {
          const v = e.target.value; setVal(name, v);
          if (name === "bransament_kw") setVal("cef", { ...(form.cef || {}), grid: { ...(form.cef?.grid || {}), bransament_kw: Number(v) || "" } });
          if (name === "inverter_count" && form.cef?.inverters?.length) {
            const count = Math.max(1, Number(v) || 1);
            setVal("cef", { ...form.cef, inverters: form.cef.inverters.map((x, i) => i ? x : { ...x, count }) });
          }
          if (name === "battery_count" && form.cef?.inverters?.[0]?.battery_mode === "own") {
            const modules = Math.max(1, Number(v) || 1);
            setVal("cef", { ...form.cef, inverters: form.cef.inverters.map((x, i) => i ? x : { ...x, battery: { ...(x.battery || {}), modules } }) });
          }
          if (name === "power" && form.cef?.inverters?.length) {
            const count = Math.max(1, Number(form.inverter_count) || form.cef.inverters.reduce((n, x) => n + (Number(x.count) || 1), 0));
            setVal("cef", { ...form.cef, inverters: form.cef.inverters.map((x, i) => i ? x : { ...x, p_limit_kw: Number(v) ? Number(v) / count : "" }) });
          }
        }} />}
    </label>
  );
  const catalogSelect = (kind, label) => {
    const query = catalogSearch[kind] || "";
    const matches = options[kind].filter((x) => `${x.brand_model} ${x.type || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
    return (
      <label key={kind} className="den-field">
        <span>{label}</span>
        <input className="den-input mb-1" value={query} onChange={(e) => setCatalogSearch((prev) => ({ ...prev, [kind]: e.target.value }))}
          placeholder="Caută după marcă sau model..." aria-label={`Caută ${label} în catalog`} data-testid={`catalog-search-${kind}`} />
        <select className="den-input" style={selectStyle} value={selected[kind] || ""} onChange={(e) => { choose(kind, e.target.value); setCatalogSearch((prev) => ({ ...prev, [kind]: "" })); }}>
          <option value="">Alege din catalog ({matches.length})...</option>
          {matches.map((x) => <option key={x.id} value={x.id}>{x.brand_model} {x.p_nom_kw ? `· ${x.p_nom_kw} kW` : x.w ? `· ${x.w} W` : x.kwh ? `· ${x.kwh} kWh` : ""}{!(x.datasheet && x.conformity) ? " · documente lipsă" : ""}</option>)}
        </select>
        {query && matches.length === 0 && <small className="block mt-1 text-amber-700">Modelul nu este încă în catalog; adaugă-l împreună cu fișa tehnică și certificatul de conformitate.</small>}
        {selected[kind] && (() => { const x = options[kind].find((v) => v.id === selected[kind]); return x && <small className="block mt-1" style={{ color: "var(--muted)" }}>Date preluate din catalog{x.datasheet && x.conformity ? " · fișă și conformitate disponibile" : " · verifică fișa tehnică și conformitatea"}</small>; })()}
      </label>
    );
  };

  return <div className="space-y-5" data-testid="prosumator-quick-form">
    <section>
      <h3 className="text-sm font-bold mb-3">1. Client și loc de consum</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="den-field sm:col-span-2"><span>{title(field(cfg, "client_name"), "Beneficiar / client")} *</span>
          <select className="den-input" value={form.client_name || ""} onChange={(e) => {
            const v = e.target.value;
            const c = clients.find((x) => x.label === v);
            setVal("client_name", v);
            setVal("client_id", c?.id || "");
            // Switching client replaces the identity and supply-point fields together,
            // so the dossier cannot silently keep another client's POD or address.
            for (const [k, value] of [
              ["cnp", c?.cnp || c?.idcode || ""], ["phone", c?.phone || ""], ["email", c?.email || ""],
              ["hq_address", c?.hq_address || ""], ["address", c?.address || ""], ["county", c?.county || ""],
              ["pod", c?.pod || ""], ["operator", c?.operator || ""], ["cf_nr", c?.cf_nr || ""],
              ["cadastral_nr", c?.cadastral_nr || ""], ["supplier", c?.supplier || ""],
            ]) setVal(k, value);
            setVal("address_same_as_ci", false);
          }}><option value="">Alege client...</option>{form.client_name && !clients.some((x) => x.label === form.client_name) && <option value={form.client_name}>{form.client_name} · extras din document</option>}{clients.map((c) => <option key={c.id} value={c.label}>{c.label}</option>)}</select>
        </label>
        {input("cnp", "CNP / CUI")}
        {input("phone", "Telefon")}
        {input("email", "Email")}
        {input("hq_address", "Adresă din CI / sediu")}
        {input("address", "Adresa locului de consum")}
        {input("pod", "POD")}
        {input("request_type", title(field(cfg, "request_type"), "Tip cerere"), "text", field(cfg, "request_type")?.options)}
        {input("operator", "Operator de distribuție", "text", field(cfg, "operator")?.options)}
        {input("power", "Putere evacuată cerută (kW)", "number")}
        {input("supply", title(field(cfg, "supply"), "Branșament"), "text", field(cfg, "supply")?.options)}
        {input("bransament_kw", "Putere branșament aprobată / cerută (kW)", "number")}
        <label className="den-field sm:col-span-2"><span>Adresă loc de consum</span><span className="flex items-center gap-2 min-h-10"><input type="checkbox" checked={form.address_same_as_ci === true} onChange={(e) => { setVal("address_same_as_ci", e.target.checked); if (e.target.checked) setVal("address", form.hq_address || ""); }} /> Este aceeași cu adresa din CI</span></label>
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Încarcă CI, factura și actul de proprietate cu „Import din PDF (AI)”. Verifică datele extrase înainte de salvare.</p>
    </section>
    <section className="border-t pt-4" style={{ borderColor: "var(--line)" }}>
      <h3 className="text-sm font-bold mb-3">2. Echipamente</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        {catalogSelect("inverter", "Invertor")}
        {input("inverter_count", "Număr invertoare", "number")}
        {catalogSelect("panel", "Panou fotovoltaic")}
        {input("panel_count", "Număr total panouri", "number")}
        {catalogSelect("battery", "Baterie (opțional)")}
        {input("battery_count", "Număr baterii", "number")}
        {catalogSelect("meter", "Smart meter (opțional)")}
        <label className="den-field"><span>Backup</span><span className="flex items-center gap-2 min-h-10"><input type="checkbox" checked={form.backup === true || form.backup === "Da"} onChange={(e) => { const on = e.target.checked; setVal("backup", on); setVal("anti_relay_present", on ? "DA" : "NU"); const cef = form.cef || { grid: {}, inverters: [], shared_batteries: [] }; setVal("cef", { ...cef, grid: { ...(cef.grid || {}), anti_required: on }, inverters: (cef.inverters || []).map((x, i) => i ? x : { ...x, backup: { ...(x.backup || {}), enabled: on } }) }); }} /> Instalația include ieșire backup</span></label>
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Datele tehnice sunt preluate din catalog și folosite de configuratorul schemei. Valorile calculate sunt propuneri pentru verificare; măsurătorile și rezultatele testelor trebuie introduse din documentele reale.</p>
      {problem && <p className="text-xs mt-2 text-amber-700">{problem}</p>}
      {catalogLoading && <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Se încarcă modelele din catalog…</p>}
      {!catalogLoading && catalog.length === 0 && !problem && <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Catalog gol. Adaugă modelele și fișele lor în Catalog echipamente.</p>}
    </section>
  </div>;
}
