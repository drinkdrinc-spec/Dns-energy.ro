import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, API, fileUrl } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X, LayoutGrid, List, Filter, ChevronRight, Archive, Upload } from "lucide-react";
import { toast } from "sonner";
import { AiImportButton, GeneratedDocs } from "@/components/ProsumatorTools";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs, uploadFile } from "@/components/dossier/ClientDocs";
import { SignRequests } from "@/components/sign/SignRequests";
import { SldPanel } from "@/components/sld/SldPanel";
import { AssignBox } from "@/components/AssignBox";
import { useAuth } from "@/context/AuthContext";
import { PowerDossier, SimpleDossierBtn } from "@/components/dossier/PowerDossier";
import { AtrDossier } from "@/components/dossier/AtrDossier";
import { PifPanel } from "@/components/dossier/PifPanel";
import { AiDossierCheck } from "@/components/ai/AiDossierCheck";
import { AiDraft } from "@/components/ai/AiDraft";
import { DiuDossier } from "@/components/dossier/DiuDossier";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { can } from "@/lib/plan";
import { DossierTimeline } from "@/components/dossier/DossierTimeline";
import { DossierMessages } from "@/components/dossier/DossierMessages";
import { F } from "@/components/cef/F";

const PROSUM_STATUS_MAP = { "În pregătire": "CER", "Depus la operator": "Dosar depus", "ATR emis": "Factură ATR", "În execuție": "Așteaptă instalare", "Punere în funcțiune": "PV Teste / PIF", "Prosumator activ": "Finalizat" };
const displayStatus = (item) => PROSUM_STATUS_MAP[item.status] || item.status || "CER";
const GUIDED_STEPS = [
  ["client", "Client și loc de consum", "dossier-section-client"],
  ["installation", "Instalație și echipamente", "dossier-section-equipment"],
  ["acts", "Acte și responsabili", "dossier-section-documents"],
  ["documents", "Documente și semnare", "generated-docs"],
  ["submission", "Depunere", "timeline-od-messages"],
  ["commissioning", "Punere în funcțiune", "dossier-section-pif-tools"],
];
const RO_COUNTIES = ["Alba", "Arad", "Argeș", "Bacău", "Bihor", "Bistrița-Năsăud", "Botoșani", "Brăila", "Brașov", "București", "Buzău", "Călărași", "Caraș-Severin", "Cluj", "Constanța", "Covasna", "Dâmbovița", "Dolj", "Galați", "Giurgiu", "Gorj", "Harghita", "Hunedoara", "Ialomița", "Iași", "Ilfov", "Maramureș", "Mehedinți", "Mureș", "Neamț", "Olt", "Prahova", "Sălaj", "Satu Mare", "Sibiu", "Suceava", "Teleorman", "Timiș", "Tulcea", "Vâlcea", "Vaslui", "Vrancea"];
const LOCATION_FIELDS = ["address", "county", "locality", "postal_code", "pod", "operator", "location_code", "supplier", "approved_kva", "existing_supply", "location_new", "cadastral_nr", "cf_nr"];

function Field({ f, value, onChange, refOptions, ai, allowNewReference = false }) {
  if (f.type === "section") return <h3 className="sm:col-span-2 mt-3 pt-3 border-t text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h3>;
  const optionValue = (option) => Array.isArray(option) ? option[0] : option;
  const optionLabel = (option) => Array.isArray(option) ? option[1] : option;
  const common = { className: "den-input", value: value ?? "", onChange: (e) => onChange(f.name, e.target.value), placeholder: f.placeholder || "", readOnly: !!f.readOnly, "data-testid": `field-${f.name}` };
  return (
    <div className={`den-field ${f.full ? "sm:col-span-2" : ""}`}>
      {f.type === "checkbox" ? <label className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm" style={{ borderColor: "var(--line)" }}><input type="checkbox" checked={!!value} onChange={(e) => onChange(f.name, e.target.checked)} data-testid={`field-${f.name}`} /><span>{f.label}</span></label> : <><label>{f.label}</label>
      {f.type === "textarea" ? (
        <><textarea {...common} rows={3} />{ai && <AiDraft module={ai.module} field={f.name} label={f.label} form={ai.form} onApply={onChange} />}</>
      ) : f.type === "select" ? (
        <select {...common}><option value="">Alege...</option>{value && !f.options.some((o) => optionValue(o) === value) && <option value={value}>{value}</option>}{f.options.map((o) => <option key={optionValue(o)} value={optionValue(o)}>{optionLabel(o)}</option>)}</select>
      ) : f.type === "ref" && allowNewReference ? (
        <><input {...common} list={`options-${f.name}`} autoComplete="off" /><datalist id={`options-${f.name}`}>{(refOptions[f.ref] || []).map((o) => <option key={o.id} value={o.label} />)}</datalist>
          <div className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>Alege un client existent sau scrie numele unui client nou; acesta va fi adăugat automat în registru la salvarea dosarului.</div></>
      ) : f.type === "ref" ? (
        <select {...common}><option value="">Alege...</option>{value && !(refOptions[f.ref] || []).some((o) => o.label === value) && <option value={value}>{value} (nou)</option>}{(refOptions[f.ref] || []).map((o) => <option key={o.id} value={o.label}>{o.label}</option>)}</select>
      ) : (
        <input {...common} type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} step={f.type === "number" ? "any" : undefined} />
      )}</>}
    </div>
  );
}

function RequestLoads({ form, setVal }) {
  const rows = form.receptors || [];
  const number = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
  const setCefField = (name, value) => onChange({ cef: { ...cef, [name]: value } });
  const setGridField = (name, value) => onChange({ cef: { ...cef, grid: { ...(cef.grid || {}), [name]: value } } });
  const total = rows.reduce((sum, row) => sum + number(row.kw) * Math.max(0, number(row.qty)), 0);
  const requested = number(form.requested_consumption_kw);
  const complete = rows.length > 0 && requested > 0 && Math.abs(total - requested) < 0.01;
  const update = (index, name, value) => setVal("receptors", rows.map((row, i) => i === index ? { ...row, [name]: value } : row));
  return <section className="sm:col-span-2 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="request-loads">
    <div className="grid sm:grid-cols-2 gap-3">
      <div className="den-field"><label>Putere maximă cerută pentru consum (kW)</label><input className="den-input" type="number" min="0" step="any" value={form.requested_consumption_kw ?? ""} onChange={(e) => setVal("requested_consumption_kw", e.target.value)} data-testid="requested-consumption" /></div>
      <div className="den-field"><label>Putere aprobată existentă (kW)</label><input className="den-input" type="number" min="0" step="any" value={form.approved_consumption_kw ?? ""} onChange={(e) => setVal("approved_consumption_kw", e.target.value)} data-testid="approved-consumption" /></div>
    </div>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
      <div className="text-xs font-bold">Receptoare electrice</div>
      <div className="text-xs font-bold" style={{ color: rows.length && requested ? (complete ? "#15803d" : "#a16207") : "var(--muted)" }} data-testid="receptor-total">
        Σ {total.toFixed(2).replace(".", ",")} / {requested ? requested.toFixed(2).replace(".", ",") : "—"} kW{rows.length && requested ? (complete ? " ✓" : " · verifică totalul") : ""}
      </div>
    </div>
    <div className="mt-2 space-y-2">
      {rows.map((row, index) => <div key={row.id || index} className="grid grid-cols-12 gap-2" data-testid={`request-receptor-${index}`}>
        <input className="den-input col-span-12 sm:col-span-6 min-w-0" aria-label={`Denumire receptor ${index + 1}`} placeholder="Denumire receptor" value={row.name || ""} onChange={(e) => update(index, "name", e.target.value)} />
        <input className="den-input col-span-5 sm:col-span-3 min-w-0" aria-label={`Putere kW receptor ${index + 1}`} type="number" min="0" step="any" placeholder="kW/buc." value={row.kw ?? ""} onChange={(e) => update(index, "kw", e.target.value)} />
        <input className="den-input col-span-5 sm:col-span-2 min-w-0" aria-label={`Cantitate receptor ${index + 1}`} type="number" min="1" step="1" placeholder="Buc." value={row.qty ?? 1} onChange={(e) => update(index, "qty", e.target.value)} />
        <button type="button" className="col-span-2 sm:col-span-1 grid min-h-10 place-items-center rounded-lg border" style={{ borderColor: "var(--line)" }} aria-label={`Șterge receptorul ${index + 1}`} onClick={() => setVal("receptors", rows.filter((_, i) => i !== index))}><Trash2 size={14} style={{ color: "#b33333" }} /></button>
      </div>)}
    </div>
    <button type="button" className="mt-3 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--green)" }} onClick={() => setVal("receptors", [...rows, { id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`, qty: 1 }])} data-testid="add-request-receptor"><Plus size={14} /> Adaugă receptor</button>
  </section>;
}

function SameAddress({ form, setVal }) {
  return <label className="flex items-center gap-2 text-xs font-medium sm:col-span-2" style={{ color: "var(--muted)" }} data-testid="same-as-hq-toggle">
    <input type="checkbox" checked={!!form.address_same_as_hq} onChange={(e) => setVal("address_same_as_hq", e.target.checked)} />
    Adresa locului de consum este aceeași cu domiciliul / sediul clientului
  </label>;
}

function QuickEquipment({ form, catalog, onChange, onSave, isDirty, saveError }) {
  const cef = form.cef || { grid: {}, inverters: [], shared_batteries: [] };
  const inverters = cef.inverters?.length ? cef.inverters : [{}];
  const options = (category) => catalog.filter((item) => item.category === category);
  const byId = (id, category) => options(category).find((item) => item.id === id);
  const number = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
  const setInv = (index, patch, legacy = {}) => {
    const nextInverters = [...inverters];
    nextInverters[index] = { ...(nextInverters[index] || {}), ...patch };
    const nextCef = { ...cef, grid: { ...(cef.grid || {}), ...(form.supply ? { supply: form.supply } : {}) }, inverters: nextInverters };
    const configured = nextInverters.filter((item) => item.brand_model || item.catalog_id);
    const panelCount = configured.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels), 0)), 0);
    const pvKwp = configured.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels) * number(item.panel_w) / 1000, 0)), 0);
    const inverterKw = configured.reduce((sum, item) => sum + number(item.p_nom_kw), 0);
    const exportPower = configured.reduce((sum, item) => sum + Math.min(number(item.p_nom_kw), number(item.p_limit_kw) || number(item.p_nom_kw)), 0);
    const power = pvKwp > 0 && inverterKw > 0 ? Math.min(pvKwp, exportPower) : 0;
    const batteryKwh = configured.filter((item) => item.battery_mode === "own")
      .reduce((sum, item) => sum + number(item.battery?.kwh) * Math.max(1, number(item.battery?.modules) || 1), 0);
    const first = configured[0] || {};
    const selectedBattery = configured.find((item) => item.battery_mode === "own")?.battery;
    onChange({
      cef: nextCef,
      panel_count: panelCount || "",
      _kwp: pvKwp || "",
      inverter_count: configured.length || "",
      inverter_kw: inverterKw || "",
      inverter: first.brand_model || "",
      panels: first.panel_model || "",
      panel_w: first.panel_w || "",
      battery: configured.find((item) => item.battery_mode === "own")?.battery?.model || "",
      battery_kwh: batteryKwh || "",
      battery_v: selectedBattery?.voltage || "",
      battery_ah: selectedBattery?.ah || "",
      system_type: batteryKwh ? "Hibrid cu baterie" : "On-grid",
      ...(configured.length ? { power: power || "" } : {}),
      ...legacy,
    });
  };
  const updateInverter = (index, patch) => setInv(index, patch);
  const chooseInverter = (index, id) => {
    const item = byId(id, "Invertor");
    const inv = inverters[index] || {};
    if (!item) return;
    setInv(index, { ...inv, catalog_id: item.id, brand_model: item.brand_model, type: item.type || "Hibrid", phases: item.phases || form.supply || "Trifazat",
      p_nom_kw: item.p_nom_kw, p_max_kw: item.p_max_kw || item.p_nom_kw, vdc_max: item.vdc_max, mppt_min: item.mppt_min,
      mppt_max: item.mppt_max, mppt_count: item.mppt_count || 1, imax_mppt: item.imax_mppt,
      ac: { cable_type: "RVK", material: "Cu", install: "C", section: 6, ...(inv.ac || {}) },
      dc: { cable_type: "H1Z2Z2-K", material: "Cu", section: 6, ...(inv.dc || {}) },
      strings: inv.strings || [], battery_mode: inv.battery_mode || "none" });
  };
  const choosePanel = (index, id) => {
    const item = byId(id, "Panou");
    const inv = inverters[index] || {};
    if (!item) return;
    setInv(index, { ...inv, panel_catalog_id: item.id, panel_model: item.brand_model, panel_w: item.w, panel_voc: item.voc,
      panel_vmp: item.vmp, panel_isc: item.isc, panel_coef_voc: item.coef_voc });
  };
  const setStrings = (index, value) => {
    const inv = inverters[index] || {};
    const old = inv.strings || [];
    const counts = value.split(",").map((part) => part.trim()).filter(Boolean);
    const mpptCount = Math.max(1, Number(inv.mppt_count) || 1);
    const strings = counts.map((part, i) => ({ ...(old[i] || {}), panels: Number(part) || "", mppt: old[i]?.mppt || (i % mpptCount) + 1 }));
    setInv(index, { ...inv, strings_text: value, strings });
  };
  const chooseBattery = (index, id) => {
    const item = byId(id, "Baterie");
    const inv = inverters[index] || {};
    if (!item) {
      setInv(index, { ...inv, battery_mode: "none", battery: undefined });
      return;
    }
    const modules = Math.max(1, Number(inv.battery?.modules) || 1);
    const battery = { ...(inv.battery || {}), catalog_id: item.id, model: item.brand_model, kwh: item.kwh,
      ah: item.ah, voltage: item.voltage, coupling: item.coupling || "DC", modules };
    setInv(index, { ...inv, battery_mode: "own", battery });
  };
  const setBatteryModules = (index, value) => {
    const inv = inverters[index] || {};
    const modules = Math.max(1, Number(value) || 1);
    setInv(index, { ...inv, battery: { ...(inv.battery || {}), modules } });
  };
  const addInverter = () => setInv(inverters.length, { id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`, phases: form.supply || "Trifazat", type: "Hibrid", strings: [], battery_mode: "none", ac: { material: "Cu", install: "C", section: 6 }, dc: { cable_type: "H1Z2Z2-K", material: "Cu", section: 6 } });
  const removeInverter = (index) => {
    const next = inverters.filter((_, i) => i !== index);
    const configured = next.filter((item) => item.brand_model || item.catalog_id);
    const panelCount = configured.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels), 0)), 0);
    const pvKwp = configured.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels) * number(item.panel_w) / 1000, 0)), 0);
    const inverterKw = configured.reduce((sum, item) => sum + number(item.p_nom_kw), 0);
    const batteryKwh = configured.filter((item) => item.battery_mode === "own")
      .reduce((sum, item) => sum + number(item.battery?.kwh) * Math.max(1, number(item.battery?.modules) || 1), 0);
    const exportPower = configured.reduce((sum, item) => sum + Math.min(number(item.p_nom_kw), number(item.p_limit_kw) || number(item.p_nom_kw)), 0);
    onChange({ cef: { ...cef, inverters: next }, panel_count: panelCount || "", _kwp: pvKwp || "", inverter_count: configured.length || "", inverter_kw: inverterKw || "",
      inverter: configured[0]?.brand_model || "", panels: configured[0]?.panel_model || "", panel_w: configured[0]?.panel_w || "",
      battery: configured.find((item) => item.battery_mode === "own")?.battery?.model || "", battery_kwh: batteryKwh || "",
      battery_v: configured.find((item) => item.battery_mode === "own")?.battery?.voltage || "",
      battery_ah: configured.find((item) => item.battery_mode === "own")?.battery?.ah || "",
      power: pvKwp && inverterKw ? Math.min(pvKwp, exportPower) : "", system_type: batteryKwh ? "Hibrid cu baterie" : "On-grid" });
  };
  const optimizer = (cef.auxiliary_equipment || []).find((item) => item.category === "Optimizator") || {};
  const previousInstallation = cef.previous_installation || {};
  const removedInverters = previousInstallation.removed_inverters || [];
  const setPreviousInstallation = (patch) => onChange({ cef: { ...cef, previous_installation: { ...previousInstallation, ...patch } } });
  const setOptimizer = (id, model = optimizer.model || "") => {
    const rest = (cef.auxiliary_equipment || []).filter((item) => item.category !== "Optimizator");
    if (id === "none") return onChange({ cef: { ...cef, auxiliary_equipment: rest } });
    const item = byId(id, "Optimizator");
    const next = id === "manual" ? { id: optimizer.id || `optimizer-${Date.now()}`, category: "Optimizator", model, quantity: optimizer.quantity || 1 }
      : item ? { id: item.id, catalog_id: item.id, category: "Optimizator", model: item.brand_model, quantity: optimizer.quantity || 1 } : null;
    if (next) onChange({ cef: { ...cef, auxiliary_equipment: [...rest, next] } });
  };
  const configuredCount = inverters.filter((item) => item.brand_model || item.catalog_id).length;
  const panelTotal = inverters.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels), 0)), 0);
  const pvTotal = inverters.reduce((sum, item) => sum + (item.no_panels ? 0 : (item.strings || []).reduce((n, string) => n + number(string.panels) * number(item.panel_w) / 1000, 0)), 0);
  return <section className="sm:col-span-2 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="new-dossier-equipment">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b pb-3" style={{ borderColor: "var(--line)" }}><div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: isDirty ? "#e98a22" : "var(--green)" }} /><h3 className="text-sm font-bold">CEF — invertoare, panouri, baterii</h3>{isDirty && <span className="text-[10px] font-bold text-amber-700">Modificări nesalvate</span>}</div><span className="text-xs" style={{ color: "var(--muted)" }}>{configuredCount} rând(uri)</span></div>
    {saveError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800" role="alert">Salvarea a eșuat: {saveError}</p>}
    <label className="mb-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={!!cef.extension_existing} onChange={(event) => setCefField("extension_existing", event.target.checked)} data-testid="cef-extension-existing" /> Extindere CEF existent (instalația veche rămâne în funcțiune)</label>
    <div className="mb-3 flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs" style={{ color: "var(--muted)" }}>Alege modelele din catalog; parametrii disponibili se preiau automat și intră în dimensionare și schema monofilară.</p></div><div className="flex flex-wrap gap-2 rounded-lg border border-dashed p-2" style={{ borderColor: "var(--line)", background: "var(--bg)" }}><span className="self-center text-[11px] font-semibold" style={{ color: "var(--muted)" }}>Nu găsești un echipament?</span><button type="button" onClick={addInverter} className="rounded-md border bg-white px-2.5 py-1.5 text-xs font-bold" style={{ borderColor: "var(--line)" }}>+ Invertor</button><button type="button" onClick={() => { const inv = inverters[0] || {}; updateInverter(0, { ...inv, panel_catalog_id: "", panel_model: "", panel_w: "", no_panels: false }); document.querySelector('[data-testid="quick-panel-model-0"]')?.focus(); }} className="rounded-md border bg-white px-2.5 py-1.5 text-xs font-bold" style={{ borderColor: "var(--line)" }}>+ Panou</button><button type="button" onClick={() => updateInverter(0, { ...(inverters[0] || {}), battery_mode: "own", battery: { ...(inverters[0]?.battery || {}), modules: inverters[0]?.battery?.modules || 1 } })} className="rounded-md border bg-white px-2.5 py-1.5 text-xs font-bold" style={{ borderColor: "var(--line)" }}>+ Baterie</button><button type="button" onClick={() => { setGridField("meter_manual", true); document.querySelector('[data-testid="quick-meter-model"]')?.focus(); }} className="rounded-md border bg-white px-2.5 py-1.5 text-xs font-bold" style={{ borderColor: "var(--line)" }}>+ Contor</button></div></div>
    <div className="space-y-3">
      {inverters.map((inv, index) => {
        const selectedBatteryId = inv.battery_mode === "own" ? (inv.battery?.catalog_id || "manual") : "none";
        const inverterValue = inv.catalog_id || (inv.brand_model ? "manual" : "");
        const panelValue = inv.panel_catalog_id || (inv.panel_model ? "manual" : "");
        return <div key={inv.id || `inverter-${index}`} className="rounded-xl border bg-white p-3 sm:p-4" style={{ borderColor: "var(--line)" }} data-testid={`quick-inverter-card-${index}`}>
          <div className="mb-3 flex items-center justify-between gap-2"><h4 className="text-sm font-bold">Invertor {index + 1}</h4>{(inverters.length > 1 || configuredCount > 0) && <button type="button" onClick={() => removeInverter(index)} className="text-xs font-semibold text-red-700">Elimină</button>}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={!!inv.existing} onChange={(e) => updateInverter(index, { existing: e.target.checked })} />Existent (rămâne în funcțiune)</label>
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={inv.type === "Invertor de baterie (AC)"} onChange={(e) => updateInverter(index, { type: e.target.checked ? "Invertor de baterie (AC)" : (byId(inv.catalog_id, "Invertor")?.type || "Hibrid") })} />Invertor-încărcător de baterie</label>
            <label className="sm:col-span-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={!!inv.no_panels} onChange={(e) => updateInverter(index, { no_panels: e.target.checked, ...(e.target.checked ? { strings: [], strings_text: "", panel_catalog_id: "", panel_model: "", panel_w: "" } : {}) })} />Fără panouri (doar baterie)</label>
            <F label="Invertor · model și putere" value={inverterValue} options={[["manual", "Introduc manual modelul"], ...options("Invertor").map((item) => [item.id, `${item.brand_model} · ${item.p_nom_kw ?? "—"} kW`])]} onChange={(id) => {
              if (id === "manual") updateInverter(index, { catalog_id: "", brand_model: inv.brand_model || "", p_nom_kw: inv.p_nom_kw || "" }); else chooseInverter(index, id);
            }} testid={`quick-inverter-${index}`} />
            {(!inv.catalog_id || inv.catalog_id === "manual") && <><F label="Model invertor" value={inv.brand_model} onChange={(v) => updateInverter(index, { brand_model: v })} testid={`quick-inverter-model-${index}`} /><F label="Putere invertor (kW)" type="number" value={inv.p_nom_kw} onChange={(v) => updateInverter(index, { p_nom_kw: v })} testid={`quick-inverter-power-${index}`} /></>}
            <F label="Limitare putere injectată (kW)" type="number" value={inv.p_limit_kw} onChange={(v) => updateInverter(index, { p_limit_kw: v })} testid={`quick-inverter-limit-${index}`} />
            {!inv.no_panels && <><F label="Panou · model și putere" value={panelValue} options={[["manual", "Introduc manual modelul"], ...options("Panou").map((item) => [item.id, `${item.brand_model} · ${item.w ?? "—"} W`])]} onChange={(id) => {
              if (id === "manual") updateInverter(index, { panel_catalog_id: "", panel_model: inv.panel_model || "", panel_w: inv.panel_w || "" }); else choosePanel(index, id);
            }} testid={`quick-panel-${index}`} />
            {(!inv.panel_catalog_id || inv.panel_catalog_id === "manual") && <><F label="Model panou" value={inv.panel_model} onChange={(v) => updateInverter(index, { panel_model: v })} testid={`quick-panel-model-${index}`} /><F label="Putere panou (W)" type="number" value={inv.panel_w} onChange={(v) => updateInverter(index, { panel_w: v })} testid={`quick-panel-power-${index}`} /></>}
            <div className="sm:col-span-2"><F label="Panouri pe stringuri (ex.: 12, 12)" value={inv.strings_text ?? (inv.strings || []).map((item) => item.panels).filter(Boolean).join(", ")} onChange={(v) => setStrings(index, v)} testid={`quick-strings-${index}`} /><p className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>Un număr pentru fiecare string; distribuția pe MPPT se face automat.</p>{(inv.strings || []).map((string, si) => <p key={si} className="mt-1 rounded-md px-2 py-1 text-[10px]" style={{ background: "var(--bg)", color: "var(--muted)" }}>String {si + 1}: {number(string.panels)} × {inv.panel_model || "panou"} {number(inv.panel_w) ? `${number(inv.panel_w)} W` : ""} = {(number(string.panels) * number(inv.panel_w) / 1000).toFixed(2)} kWp</p>)}</div></>}
            <F label="Baterie" value={selectedBatteryId} options={[["none", "Fără baterie"], ["manual", "Baterie introdusă manual"], ...options("Baterie").map((item) => [item.id, `${item.brand_model} · ${item.kwh ?? "—"} kWh`])]} onChange={(id) => {
              if (id === "none") chooseBattery(index, "");
              else if (id === "manual") updateInverter(index, { battery_mode: "own", battery: { ...(inv.battery || {}), modules: inv.battery?.modules || 1 } });
              else chooseBattery(index, id);
            }} testid={`quick-battery-${index}`} />
            {selectedBatteryId !== "none" && <>
              {selectedBatteryId === "manual" && <><F label="Model baterie" value={inv.battery?.model} onChange={(v) => updateInverter(index, { battery: { ...(inv.battery || {}), model: v } })} testid={`quick-battery-model-${index}`} /><F label="Capacitate (kWh/modul)" type="number" value={inv.battery?.kwh} onChange={(v) => updateInverter(index, { battery: { ...(inv.battery || {}), kwh: v } })} testid={`quick-battery-power-${index}`} /></>}
              <F label="Număr unități baterie" type="number" value={inv.battery?.modules || 1} onChange={(v) => setBatteryModules(index, v)} testid={`quick-battery-units-${index}`} />
              <F label="Cuplaj baterie" value={inv.battery?.coupling || "DC"} options={[["DC", "DC (hibrid)"], ["AC", "AC (retrofit)"]]} onChange={(v) => updateInverter(index, { battery: { ...(inv.battery || {}), coupling: v } })} testid={`quick-battery-coupling-${index}`} />
            </>}
          </div>
          {(() => { const invItem = byId(inv.catalog_id, "Invertor"); const panelItem = byId(inv.panel_catalog_id, "Panou"); const batteryItem = byId(inv.battery?.catalog_id, "Baterie"); return (invItem || panelItem || batteryItem) && <div className="mt-3 space-y-1 text-[10px]">{[["invertor", invItem], ["panou", panelItem], ["baterie", batteryItem]].filter(([, item]) => item).map(([label, item]) => <p key={label} style={{ color: "var(--muted)" }}>{label}: {item.datasheet?.storage_path || item.datasheet_url ? <a className="font-bold" style={{ color: "var(--green)" }} href={item.datasheet?.storage_path ? fileUrl(item.datasheet.storage_path) : item.datasheet_url} target="_blank" rel="noreferrer">fișă tehnică ↗</a> : <span>fișă lipsă</span>} · {item.conformity?.storage_path || item.conformity_url ? <a className="font-bold" style={{ color: "var(--green)" }} href={item.conformity?.storage_path ? fileUrl(item.conformity.storage_path) : item.conformity_url} target="_blank" rel="noreferrer">conformitate ↗</a> : <span>conformitate lipsă</span>}</p>)}</div>; })()}
          {inv.strings?.length > 0 && <div className="mt-3 text-xs font-semibold" style={{ color: "var(--green)" }}>{inv.strings.reduce((sum, item) => sum + number(item.panels), 0)} panouri · {(inv.strings.reduce((sum, item) => sum + number(item.panels), 0) * number(inv.panel_w) / 1000).toFixed(2)} kWp</div>}
        </div>;
      })}
    </div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <F label="Optimizatoare" value={optimizer.catalog_id || (optimizer.model ? "manual" : "none")} options={[["none", "Fără optimizatoare"], ["manual", "Introduc manual modelul"], ...options("Optimizator").map((item) => [item.id, item.brand_model])]} onChange={(id) => setOptimizer(id)} testid="quick-optimizer" />
      {((optimizer.catalog_id || optimizer.model) && !optimizer.catalog_id) && <F label="Model optimizator" value={optimizer.model} onChange={(value) => setOptimizer("manual", value)} testid="quick-optimizer-model" />}
      {cef.grid?.meter_manual && <F label="Model contor" value={cef.grid?.meter || ""} onChange={(value) => setGridField("meter", value)} testid="quick-meter-model" />}
    </div>
    <details className="mt-4 rounded-xl border bg-white px-3 py-3" style={{ borderColor: "var(--line)" }} data-testid="previous-installation">
      <summary className="cursor-pointer text-sm font-bold">Instalația anterioară și înlocuiri</summary>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>Completează când un invertor existent a fost demontat. Apare separat în notificare și nu intră în puterile instalației noi.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <F label="Certificat de racordare existent · număr" value={previousInstallation.certificate_no} onChange={(v) => setPreviousInstallation({ certificate_no: v })} testid="previous-certificate-no" />
        <F label="Data certificatului" type="date" value={previousInstallation.certificate_date} onChange={(v) => setPreviousInstallation({ certificate_date: v })} testid="previous-certificate-date" />
      </div>
      <div className="mt-4 space-y-2">
        {removedInverters.map((inv, i) => <div key={i} className="grid gap-2 rounded-lg border p-2 sm:grid-cols-[minmax(0,1fr)_140px_auto] sm:items-end" style={{ borderColor: "var(--line)" }}>
          <F label={`Invertor demontat ${i + 1} · model`} value={inv.model || ""} onChange={(v) => setPreviousInstallation({ removed_inverters: removedInverters.map((x, j) => j === i ? { ...x, model: v } : x) })} testid={`removed-inverter-${i}-model`} />
          <F label="Putere (kW) · informativ" type="number" value={inv.power_kw} onChange={(v) => setPreviousInstallation({ removed_inverters: removedInverters.map((x, j) => j === i ? { ...x, power_kw: v } : x) })} testid={`removed-inverter-${i}-power`} />
          <button type="button" onClick={() => setPreviousInstallation({ removed_inverters: removedInverters.filter((_, j) => j !== i) })} className="rounded-lg border px-3 py-2 text-xs font-semibold text-red-700" style={{ borderColor: "var(--line)" }}>Elimină</button>
        </div>)}
      </div>
      <button type="button" onClick={() => setPreviousInstallation({ removed_inverters: [...removedInverters, { model: "", power_kw: "" }] })} className="mt-3 rounded-lg border px-3 py-2 text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>＋ Adaugă invertor demontat</button>
    </details>
    {configuredCount > 0 && <div className="mt-3 rounded-lg px-3 py-2 text-xs font-semibold" style={{ background: "#edf7f0", color: "var(--green)" }}>Total automat: {configuredCount} invertor(e) · {panelTotal} panouri · {pvTotal.toFixed(2)} kWp</div>}
    {onSave && <div className="mt-4 flex justify-end"><button type="button" onClick={onSave} className="rounded-lg px-4 py-2.5 text-xs font-bold text-white" style={{ background: "var(--green)" }}>Salvează</button></div>}
  </section>;
}

function PramModePanel({ id, form, setVal }) {
  const input = useRef(null);
  const [uploading, setUploading] = useState(false);
  const mode = form.pram_mode || "self";
  const file = form.opis?.priza?.upload;
  const modes = [["self", "Îl fac eu"], ["third_party", "Buletin de la terț"], ["none", "Fără PRAM"]];
  return <div className="p-4 pb-0 sm:px-5" data-testid="pram-mode-panel">
    <div className="grid grid-cols-3 gap-1 rounded-xl p-1" style={{ background: "var(--bg)" }} role="group" aria-label="Mod buletin PRAM">
      {modes.map(([value, label]) => <button key={value} type="button" onClick={() => setVal("pram_mode", value)} aria-pressed={mode === value} className="rounded-lg px-2 py-2 text-xs font-bold" style={mode === value ? { background: "white", color: "var(--green)", boxShadow: "0 1px 3px #0001" } : { color: "var(--muted)" }} data-testid={`pram-mode-${value}`}>{label}</button>)}
    </div>
    {mode === "third_party" && <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed p-3" style={{ borderColor: "var(--line)" }}>
      <div className="min-w-0 text-xs" style={{ color: "var(--muted)" }}>{file?.original_filename || "Atașează PDF-ul buletinului PRAM primit de la terț."}</div>
      <input ref={input} type="file" accept="application/pdf,image/*" className="hidden" data-testid="pram-third-party-input" onChange={async (event) => {
        const selected = event.target.files?.[0]; if (!selected) return;
        setUploading(true);
        try {
          const uploaded = await uploadFile(selected);
          await api.put(`/dossier/${id}/item/priza`, { upload: uploaded, status: null });
          setVal("opis", { ...(form.opis || {}), priza: { ...(form.opis?.priza || {}), upload: uploaded } });
          toast.success("Buletinul PRAM a fost atașat");
        } catch (error) { toast.error(error.response?.data?.detail || "Nu am putut atașa buletinul PRAM"); }
        finally { setUploading(false); event.target.value = ""; }
      }} />
      <button type="button" disabled={uploading} onClick={() => input.current?.click()} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-60" style={{ borderColor: "var(--line)", color: "var(--green)" }} data-testid="pram-third-party-upload"><Upload size={14} />{uploading ? "Se încarcă…" : file ? "Înlocuiește" : "Încarcă"}</button>
    </div>}
    {mode === "none" && <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>Poziția pentru buletinul PRAM va fi omisă din opis și din dosarul PDF.</p>}
  </div>;
}

function DossierFieldSections({ id, fields, form, setVal, refOptions, ai, onSaveSection, sectionLabels, baselineForm, saveErrors = {} }) {
  const sections = [];
  let current = { label: "Date dosar", fields: [] };
  fields.forEach((field) => {
    if (field.type === "section") {
      if (current.fields.length) sections.push(current);
      current = { label: field.label, fields: [] };
    } else current.fields.push(field);
  });
  if (current.fields.length) sections.push(current);
  const orderedSections = sectionLabels
    ? sectionLabels.map((label) => sections.find((section) => section.label === label)).filter(Boolean)
    : sections;

  const equipmentFields = new Set(["inverter", "inverter_kw", "inverter_count", "panels", "panel_count", "panel_w", "battery", "battery_kwh", "battery_v", "battery_ah"]);
  const setField = (name, value) => {
    setVal(name, value);
    if (name === "soil") setVal("soil_psi", ({ uscat: "1.1", mediu: "1.3", "foarte umed": "1.5" })[value] || "");
  };
  return <div className="space-y-4" data-testid="dossier-section-cards">
    {orderedSections.map((section) => {
      const visibleFields = section.label === "Date tehnice" ? section.fields.filter((field) => !equipmentFields.has(field.name)) : section.fields;
      if (!visibleFields.length) return null;
      const sectionDirty = !!baselineForm && visibleFields.some((field) => JSON.stringify(form[field.name] ?? null) !== JSON.stringify(baselineForm[field.name] ?? null));
      const sectionId = ({ Client: "dossier-section-client", "Client & date de identitate": "dossier-section-client", "Loc de consum": "dossier-section-location", Cererea: "dossier-section-request", "Branșament & măsură": "dossier-section-connection", "Date tehnice": "dossier-section-installation", "Date documente dosar": "dossier-section-documents-data", "Recepție la terminarea lucrărilor": "dossier-section-reception", "Punere în funcțiune și teste": "dossier-section-pif", "Buletin priză de pământ (valori măsurate)": "dossier-section-pram", "Tablou general și alimentare": "dossier-section-panel", "Recepție, punere în funcțiune și garanție": "dossier-section-warranty" })[section.label] || `dossier-section-${section.label.toLocaleLowerCase("ro").replace(/[^a-z0-9]+/g, "-")}`;
      return (
      <section key={section.label} id={sectionId} className="den-panel !p-0 overflow-hidden scroll-mt-24" data-testid={`dossier-section-${section.label}`}>
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5" style={{ borderColor: "var(--line)" }}>
          <div className="flex min-w-0 items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: sectionDirty ? "#e98a22" : "var(--green)" }} aria-hidden="true" />
          <h3 className="text-sm font-bold">{section.label}</h3>
          {sectionDirty && <span className="rounded-full px-2 py-1 text-[10px] font-bold" style={{ color: "#9a5c12", background: "#fff5e8" }}>Modificări nesalvate</span>}
          </div>
          {section.label === "Loc de consum" && form.pod && <span className="min-w-0 truncate text-xs" style={{ color: "var(--muted)" }}>{form.pod}</span>}
          <button type="button" onClick={() => onSaveSection(section.label)} className="shrink-0 rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }} data-testid={`save-section-${sectionId}`}>Salvează</button>
        </div>
        {saveErrors[section.label] && <p className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-red-800 sm:mx-5" role="alert">Salvarea a eșuat: {saveErrors[section.label]}</p>}
        {section.label === "Buletin priză de pământ (valori măsurate)" && <PramModePanel id={id} form={form} setVal={setVal} />}
        {(section.label !== "Buletin priză de pământ (valori măsurate)" || (form.pram_mode || "self") === "self") && <div className="grid sm:grid-cols-2 gap-4 p-4 sm:p-5">
          {visibleFields.map((field) => <div key={field.name} className={field.full ? "sm:col-span-2" : ""}><Field f={field} value={form[field.name]} onChange={setField} refOptions={refOptions} ai={ai} />
            {section.label === "Buletin priză de pământ (valori măsurate)" && field.name === "soil" && <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Alegerea stării solului completează coeficientul Ψ implicit. Verifică valoarea după condițiile măsurării.</p>}
            {section.label === "Buletin priză de pământ (valori măsurate)" && field.name === "bulletin_no" && form.bulletin_no && <p className="mt-1 inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold" style={{ color: "#166534", background: "#edf7f0" }}>Buletin nr. {form.bulletin_no} · numerotare automată pe firmă</p>}
            {section.label === "Buletin priză de pământ (valori măsurate)" && field.name === "grounding_ohm" && (() => { const measured = Number(String(form.grounding_ohm ?? "").replace(",", ".")); const psi = Number(String(form.soil_psi ?? "").replace(",", ".")); const result = measured > 0 && psi > 0 ? measured * psi : null; return <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>{result ? `Rezistență calculată: ${result.toFixed(2)} Ω${result <= Number(form.grounding_limit || 4) ? " (≤ limită ✓)" : " (peste limită)"}` : "Rezultatul calculat apare după completarea măsurătorii și a coeficientului Ψ."}</p>; })()}
            {section.label === "Loc de consum" && field.name === "address" && <div className="mt-2"><SameAddress form={form} setVal={setVal} /></div>}</div>)}
          {section.label === "Buletin priză de pământ (valori măsurate)" && <DossierExtras form={form} setVal={setVal} view="pram" />}
          {section.label === "Cererea" && <RequestLoads form={form} setVal={setVal} />}
        </div>}
      </section>
      );
    })}
  </div>;
}

function SummaryStrip({ form }) {
  const inverters = form.cef?.inverters || [];
  const asNumber = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
  const cefPanels = inverters.reduce((sum, inv) => sum + (inv.no_panels ? 0 : (inv.strings || []).reduce((n, s) => n + asNumber(s.panels), 0)), 0);
  const cefKwp = inverters.reduce((sum, inv) => sum + (inv.no_panels ? 0 : (inv.strings || []).reduce((n, s) => n + asNumber(s.panels) * asNumber(inv.panel_w) / 1000, 0)), 0);
  const cefExport = inverters.reduce((sum, inv) => {
    if (inv.no_panels) return sum;
    const nominal = asNumber(inv.p_nom_kw);
    const limit = asNumber(inv.p_limit_kw);
    return sum + (nominal ? Math.min(nominal, limit || nominal) : limit);
  }, 0);
  const ownStorage = inverters.reduce((sum, inv) => sum + (inv.battery_mode === "own" ? asNumber(inv.battery?.kwh) * Math.max(1, asNumber(inv.battery?.modules)) : 0), 0);
  const sharedIds = new Set(inverters.filter((inv) => inv.battery_mode === "shared").map((inv) => inv.shared_battery_id));
  const sharedStorage = (form.cef?.shared_batteries || []).reduce((sum, battery) => sum + (sharedIds.has(battery.id) ? asNumber(battery.kwh) * Math.max(1, asNumber(battery.modules)) : 0), 0);
  const fmt = (value) => Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2))).replace(".", ",");
  const power = cefExport || asNumber(form.power);
  const panelCount = cefPanels || asNumber(form.panel_count);
  const batteryKwh = ownStorage + sharedStorage || asNumber(form.battery_kwh);
  const inverterCount = inverters.length || asNumber(form.inverter_count);
  const inverterKw = inverters.reduce((sum, inv) => sum + asNumber(inv.p_nom_kw), 0) || asNumber(form.inverter_kw);
  const receptors = form.receptors || [];
  const receptorKw = receptors.reduce((sum, item) => sum + asNumber(item.kw) * Math.max(0, asNumber(item.qty ?? 1)), 0);
  const topology = inverters.some((inv) => inv.backup?.enabled) ? "Cu back-up" : "Rețea (fără back-up)";
  const metrics = [
    ["FV", cefKwp || asNumber(form._kwp) ? `${fmt(cefKwp || asNumber(form._kwp))} kWp` : "0 kWp"],
    ["Invertoare", inverterCount ? `${fmt(inverterKw)} kW` : "0 kW"],
    ["Putere CEF", power ? `${fmt(power)} kW` : "0 kW"],
    ["Stocare", `${fmt(batteryKwh)} kWh`],
    ["Panouri", fmt(panelCount)],
    ["Topologie", topology],
    ["Receptoare", receptors.length ? `${fmt(receptorKw)} kW` : "0 kW"],
  ];
  return <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-2 rounded-xl border p-3 mb-4" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="dossier-live-summary">
    {metrics.map(([label, value]) => <div key={label} className="min-w-0 rounded-lg px-3 py-2" style={{ background: "var(--bg)" }}>
      <div className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "var(--muted)" }}>{label}</div>
      <div className="mt-1 truncate text-xs font-bold" title={value}>{value}</div>
    </div>)}
  </div>;
}

export default function ModulePage({ moduleKey }) {
  const params = useParams();
  const key = moduleKey || params.module;
  const cfg = MODULES[key];
  const { user } = useAuth();
  const role = user?.role || "admin";
  const canDelete = role === "admin" || (role !== "limitat" && !["prosumator", "clients"].includes(key));
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null); // null=hidden, {} = open
  const [editId, setEditId] = useState(null);
  const [checks, setChecks] = useState({});
  const [refOptions, setRefOptions] = useState({});
  const [clientRecords, setClientRecords] = useState([]);
  const [q, setQ] = useState("");
  const [savedAt, setSavedAt] = useState(0);
  const [diuPre, setDiuPre] = useState(false);
  const [prosumStep, setProsumStep] = useState(1);
  const [newProsumClient, setNewProsumClient] = useState(false);
  const [newProsumLocation, setNewProsumLocation] = useState(true);
  const [equipmentCatalog, setEquipmentCatalog] = useState([]);
  const [dossierPage, setDossierPage] = useState("all");
  const [dossierView, setDossierView] = useState("kanban");
  const [mobileDossierList, setMobileDossierList] = useState(() => window.matchMedia?.("(max-width: 767px)").matches ?? false);
  const [operatorFilter, setOperatorFilter] = useState("");
  const [countyFilter, setCountyFilter] = useState("");
  const [localityFilter, setLocalityFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [archiveView, setArchiveView] = useState(false);
  const [guidedInterface, setGuidedInterface] = useState(() => localStorage.getItem("dns-dossier-interface") !== "classic");
  const [guidedStep, setGuidedStep] = useState(0);
  const savedSnapshot = useRef(null);
  const [saveErrors, setSaveErrors] = useState({});

  const load = () => api.get(`/data/${key}`).then((r) => {
    setItems(r.data);
    const eid = new URLSearchParams(window.location.search).get("edit");
    const it = eid && r.data.find((x) => x.id === eid);
    if (it) { setForm({ ...it }); setEditId(it.id); setChecks(it.checklist || {}); savedSnapshot.current = { form: JSON.stringify(it), checks: JSON.stringify(it.checklist || {}) }; window.history.replaceState(null, "", window.location.pathname); }
  }).catch(() => {});

  useEffect(() => {
    setForm(null); setEditId(null); setChecks({}); setQ("");
    load();
    const refs = [...new Set((cfg.fields || []).filter((f) => f.type === "ref").map((f) => f.ref))];
    refs.forEach((ref) => {
      api.get(`/data/${ref}`).then((r) => {
        if (key === "prosumator" && ref === "clients") setClientRecords(r.data);
        setRefOptions((prev) => ({ ...prev, [ref]: r.data.map((x) => ({ id: x.id, label: MODULES[ref].display(x) })) }));
      }).catch(() => {});
    });
    if (key === "prosumator") api.get("/data/catalog").then((r) => setEquipmentCatalog(r.data || [])).catch(() => setEquipmentCatalog([]));
    // eslint-disable-next-line
  }, [key]);

  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 767px)");
    if (!media) return undefined;
    const update = () => setMobileDossierList(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);

  useEffect(() => {
    const updateInterface = (event) => setGuidedInterface(event.detail === "guided");
    window.addEventListener("dns-dossier-interface", updateInterface);
    return () => window.removeEventListener("dns-dossier-interface", updateInterface);
  }, []);

  const openNew = () => { const today = new Date().toISOString().slice(0, 10); const draft = key === "prosumator" ? { date: today, doc_date: today, status: "CER", kind: "Persoană fizică", request_type: "Fără spor de putere", afm: "Nu", location_new: false } : {}; setForm(draft); savedSnapshot.current = { form: JSON.stringify(draft), checks: JSON.stringify({}) }; setEditId(null); setChecks({}); setSaveErrors({}); setProsumStep(1); setNewProsumClient(false); setNewProsumLocation(true); setDossierPage("all"); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); savedSnapshot.current = { form: JSON.stringify(item), checks: JSON.stringify(item.checklist || {}) }; setSaveErrors({}); setProsumStep(1); setDossierPage("all"); };
  const setVal = (name, value) => setForm((p) => {
    const next = { ...p, [name]: value };
    if (key === "prosumator" && name === "supply") next.cef = { ...(p.cef || {}), grid: { ...(p.cef?.grid || {}), supply: value } };
    if (name === "address_same_as_hq" && value) next.address = p.hq_address || "";
    if (name === "hq_address" && p.address_same_as_hq) next.address = value;
    if (name === "address" && value !== p.hq_address) next.address_same_as_hq = false;
    if (key === "prosumator" && name === "client_name") {
      const client = clientRecords.find((c) => c.name?.trim().toLocaleLowerCase() === value.trim().toLocaleLowerCase());
      const normalized = value.trim().toLocaleLowerCase();
      const previousName = String(p.client_name || "").trim().toLocaleLowerCase();
      const changedClient = previousName !== normalized;
      const lastDossier = items.filter((item) => String(item.client_name || "").trim().toLocaleLowerCase() === normalized)
        .sort((a, b) => String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")))[0] || {};
      const pick = (clientValue, dossierValue, oldValue) => clientValue || dossierValue || (changedClient ? "" : oldValue) || "";
      Object.assign(next, {
        kind: pick(client?.kind, lastDossier.kind, p.kind) || "Persoană fizică",
        cnp: pick(client?.idcode, lastDossier.cnp, p.cnp), ci_series: pick(client?.ci_series, lastDossier.ci_series, p.ci_series),
        regcom: pick(client?.regcom, lastDossier.regcom, p.regcom), bank: pick(client?.bank, lastDossier.bank, p.bank),
        iban: pick(client?.iban, lastDossier.iban, p.iban), rep_role: pick(client?.rep_role, lastDossier.rep_role, p.rep_role),
        phone: pick(client?.phone, lastDossier.phone, p.phone), email: pick(client?.email, lastDossier.email, p.email),
        address: pick(client?.address, lastDossier.address, p.address), hq_address: pick(client?.hq_address, lastDossier.hq_address, p.hq_address),
        county: pick(client?.county, lastDossier.county, p.county), locality: pick(client?.locality, lastDossier.locality, p.locality), postal_code: pick(client?.postal_code, lastDossier.postal_code, p.postal_code),
        pod: pick(client?.pod, lastDossier.pod, p.pod), operator: pick(client?.operator, lastDossier.operator, p.operator), location_code: pick(client?.location_code, lastDossier.location_code, p.location_code),
        supplier: pick(client?.supplier, lastDossier.supplier, p.supplier), approved_kva: pick(client?.approved_kva, lastDossier.approved_kva, p.approved_kva),
        existing_supply: pick(client?.existing_supply, lastDossier.existing_supply, p.existing_supply), location_new: pick(client?.location_new, lastDossier.location_new, p.location_new),
        cadastral_nr: pick(client?.cadastral_nr, lastDossier.cadastral_nr, p.cadastral_nr), cf_nr: pick(client?.cf_nr, lastDossier.cf_nr, p.cf_nr),
        rep_name: pick(client?.rep_name, lastDossier.rep_name, p.rep_name),
      });
    }
    return next;
  });
  const continueProsum = () => {
    const newClientName = form.kind === "Persoană juridică"
      ? String(form.new_company_name || "").trim()
      : [form.new_client_last_name, form.new_client_first_name].map((part) => String(part || "").trim()).filter(Boolean).join(" ");
    if (prosumStep === 1 && !(newProsumClient ? newClientName : String(form.client_name || "").trim())) { toast.error(newProsumClient ? "Completează numele clientului." : "Alege un client existent sau bifează Client nou."); return; }
    if (prosumStep === 2 && (!form.address?.trim() || !form.county?.trim() || !form.locality?.trim())) { toast.error("Completează adresa, județul și localitatea locului de consum."); return; }
    if (prosumStep === 3 && !form.request_type) { toast.error("Alege tipul cererii."); return; }
    if (key === "prosumator" && prosumStep === 1 && newProsumClient) setForm((current) => ({ ...current, client_name: newClientName }));
    if (key === "prosumator" && prosumStep === 2 && !form.request_type) setForm((current) => ({ ...current, request_type: "Fără spor de putere" }));
    setProsumStep((s) => Math.min(3, s + 1));
  };

  const save = async () => {
    if (key === "prosumator" && !editId && !form.request_type) { toast.error("Alege tipul cererii înainte de creare."); return; }
    const orig = items.find((i) => i.id === editId);
    if (key === "diu" && editId && form.status === "Predat beneficiarului" && orig?.status !== "Predat beneficiarului" && can(user, "ai_gpt")) { setDiuPre(true); return; }
    return doSave().catch(() => {});
  };
  const doSave = async () => {
    const required = (cfg.fields || []).filter((f) => f.required);
    for (const f of required) { if (!form[f.name]) { toast.error(`Completează: ${f.label.replace(" *", "")}`); return; } }
    const payload = { ...form };
    delete payload._location_key;
    delete payload.new_client_last_name;
    delete payload.new_client_first_name;
    delete payload.new_company_name;
    delete payload.allow_id_scan;
    if (cfg.checklist) payload.checklist = checks;
    try {
      if (editId) {
        const { data } = await api.put(`/data/${key}/${editId}`, payload);
        if (key === "prosumator") {
          setForm(data); setChecks(data.checklist || checks);
          savedSnapshot.current = { form: JSON.stringify(data), checks: JSON.stringify(data.checklist || checks) };
          setSaveErrors({}); toast.success("Dosarul a fost salvat"); await load(); return;
        }
      }
      else if (key === "prosumator") {
        const created = await api.post("/import/prosumator", payload);
        let dossier = created.data;
        const hasEquipment = (created.data.cef?.inverters || []).some((inv) => inv.brand_model || inv.catalog_id);
        if (hasEquipment) {
          try {
            const applied = await api.post(`/sld/${created.data.id}/apply`, { cef: created.data.cef });
            dossier = { ...created.data, cef: applied.data.cef };
            toast.success("Dosar creat. Valorile tehnice disponibile au fost calculate și pot fi verificate în dosar.");
          } catch {
            toast.warning("Dosarul a fost creat. Dimensionarea poate fi reluată după completarea echipamentelor.");
          }
        } else {
          toast.success("Dosar creat. Alege echipamentele în secțiunea Instalație pentru a completa automat dimensionarea.");
        }
        setForm(dossier); setEditId(dossier.id); setChecks(dossier.checklist || {}); savedSnapshot.current = { form: JSON.stringify(dossier), checks: JSON.stringify(dossier.checklist || {}) }; setProsumStep(1); setDossierPage("all"); load();
        return;
      }
      else await api.post(`/data/${key}`, payload);
      toast.success("Salvat cu succes");
      if (key === "diu" && editId) { setSavedAt(Date.now()); load(); return; }
      setForm(null); setEditId(null); setChecks({}); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eroare la salvare"); throw e; }
  };

  const saveDossierSection = async (label) => {
    if (!editId) return;
    try {
      const saved = await api.put(`/data/prosumator/${editId}`, { ...form, checklist: checks });
      setForm(saved.data);
      setChecks(saved.data.checklist || checks);
      savedSnapshot.current = { form: JSON.stringify(saved.data), checks: JSON.stringify(saved.data.checklist || checks) };
      setSaveErrors((current) => ({ ...current, [label]: "" }));
      toast.success(`${label}: salvat`);
      await load();
    } catch (e) {
      const message = e.response?.data?.detail || e.message || `Nu am putut salva secțiunea „${label}”`;
      setSaveErrors((current) => ({ ...current, [label]: message }));
      toast.error(message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Ștergi această înregistrare?")) return;
    await api.delete(`/data/${key}/${id}`);
    toast.success("Șters"); load();
  };

  const statusOptions = (cfg.fields || []).find((f) => f.name === "status")?.options || [];
  const archiveCutoffDate = new Date();
  archiveCutoffDate.setMonth(archiveCutoffDate.getMonth() - 6);
  const archiveCutoff = archiveCutoffDate.getTime();
  const isArchived = (item) => {
    const lastActivity = Date.parse(item.updated_at || item.created_at || "");
    return Number.isFinite(lastActivity) && lastActivity < archiveCutoff;
  };
  const archiveCount = key === "prosumator" ? items.filter(isArchived).length : 0;
  const activeItems = key === "prosumator" ? items.filter((item) => isArchived(item) === archiveView) : items;
  const hasUnsavedChanges = !!form && !!savedSnapshot.current && (
    JSON.stringify(form) !== savedSnapshot.current.form || JSON.stringify(checks) !== savedSnapshot.current.checks
  );
  const baselineForm = savedSnapshot.current ? JSON.parse(savedSnapshot.current.form) : null;
  const showGuidedStep = (index) => !guidedInterface || guidedStep === index;
  const jumpGuided = (index) => {
    const step = GUIDED_STEPS[index];
    setGuidedStep(index); setDossierPage(step[0]);
    window.setTimeout(() => document.getElementById(step[2])?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  };
  useEffect(() => {
    if (!hasUnsavedChanges) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = "Ai modificări nesalvate."; return event.returnValue; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasUnsavedChanges]);
  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return activeItems.filter((i) => (!ql || JSON.stringify(i).toLowerCase().includes(ql))
      && (!operatorFilter || i.operator === operatorFilter)
      && (!countyFilter || i.county === countyFilter)
      && (!localityFilter || i.locality === localityFilter)
      && (!clientFilter || String(i.client_name || "").toLocaleLowerCase("ro").includes(clientFilter.toLocaleLowerCase("ro"))));
  }, [activeItems, q, operatorFilter, countyFilter, localityFilter, clientFilter]);

  const changeStatus = async (item, status) => {
    try {
      await api.patch(`/data/${key}/${item.id}/status`, { status });
      setItems((prev) => prev.map((i) => i.id === item.id ? { ...i, status, updated_at: new Date().toISOString() } : i));
      toast.success("Stadiul dosarului a fost actualizat");
    } catch (e) { toast.error(e.response?.data?.detail || "Stadiul nu a putut fi actualizat"); }
  };
  const dragId = (e) => e.dataTransfer?.getData("text/plain");
  const optionValues = (key) => [...new Set(items.map((i) => i[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ro"));
  const knownLocations = useMemo(() => {
    if (key !== "prosumator" || !form?.client_name) return [];
    const wanted = String(form.client_name).trim().toLocaleLowerCase("ro");
    const seen = new Set();
    return items.filter((item) => String(item.client_name || "").trim().toLocaleLowerCase("ro") === wanted && item.address)
      .map((item) => {
        const location = Object.fromEntries(LOCATION_FIELDS.map((field) => [field, item[field] || ""]));
        const id = [location.address, location.county, location.locality, location.pod].join("|").toLocaleLowerCase("ro");
        return { ...location, id };
      }).filter((location) => { if (seen.has(location.id)) return false; seen.add(location.id); return true; });
  }, [items, form?.client_name, key]);

  const checkedCount = cfg.checklist ? cfg.checklist.filter((c) => checks[c]).length : 0;

  return (
    <div>
      {!(key === "prosumator" && editId) && <PageHeader eyebrow={cfg.eyebrow} title={cfg.title} sub={cfg.sub}
        action={<div className="flex gap-2 flex-wrap">
          {key === "prosumator" && <AiImportButton onExtracted={(d) => { setForm(d); setEditId(null); setChecks({}); }} />}
          <Btn data-testid="add-btn" onClick={form ? () => setForm(null) : openNew}>{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> {cfg.addLabel}</>}</Btn>
        </div>} />}

      {form && (
        <div className={`${key === "prosumator" && editId ? "mb-6 scroll-mt-20 space-y-4" : "den-panel mb-6 scroll-mt-20"}`} id={key === "prosumator" && editId ? "dossier-top" : undefined} data-testid="module-form">
          {key === "prosumator" && !editId ? <>
            <div className="flex items-start justify-between gap-4 mb-5">
              <div className="mb-4"><h2 className="text-lg font-bold">Dosar nou</h2><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>3 pași scurți — restul datelor se completează apoi în dosar.</p></div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-5" aria-label={`Pasul ${prosumStep} din 3`}>
              {["Client", "Loc de consum", "Tip cerere"].map((step, idx) => <div key={step} className={`rounded-lg border px-2 py-2 text-center text-[10px] sm:text-[11px] font-semibold ${prosumStep === idx + 1 ? "den-wizard-active" : ""}`} style={{ borderColor: prosumStep === idx + 1 ? "var(--green)" : "var(--line)", color: prosumStep === idx + 1 ? "var(--green)" : "var(--muted)", background: prosumStep === idx + 1 ? "#edf7f0" : "transparent" }}><span className="mr-1 inline-grid h-4 w-4 place-items-center rounded-full" style={{ background: prosumStep > idx + 1 ? "var(--green)" : "#eeeae1", color: prosumStep > idx + 1 ? "white" : "var(--muted)" }}>{prosumStep > idx + 1 ? "✓" : idx + 1}</span>{step}</div>)}
            </div>
          </> : editId && key === "prosumator" ? <div className="den-panel !p-4 sm:!p-5 mb-4" data-testid="dossier-detail-heading">
            <button type="button" onClick={() => { setForm(null); setEditId(null); }} className="mb-3 text-xs font-medium" style={{ color: "var(--muted)" }}>← Dosare</button>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0"><div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h2 className="text-xl font-extrabold" style={{ color: "var(--green)" }}>Dosar {form.number || `#${editId}`}</h2><span className="text-lg font-bold">{form.client_name || "Beneficiar neprecizat"}</span></div>
                <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{[form.locality, form.county].filter(Boolean).join(", ")}{form.operator ? ` · ${form.operator}` : ""}</p>
                <div className="mt-2 flex flex-wrap gap-2"><span className="rounded-full px-3 py-1 text-[11px] font-bold" style={{ background: "#edf7f0", color: "var(--green)" }}>{displayStatus(form)}</span>{form.request_type && <span className="rounded-full px-3 py-1 text-[11px] font-bold" style={{ background: "#fff5e8", color: "#9a5c12" }}>{form.request_type}</span>}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Btn variant="secondary" onClick={() => { const next = !guidedInterface; setGuidedInterface(next); localStorage.setItem("dns-dossier-interface", next ? "guided" : "classic"); window.dispatchEvent(new CustomEvent("dns-dossier-interface", { detail: next ? "guided" : "classic" })); setGuidedStep(0); }} data-testid="toggle-dossier-interface">{guidedInterface ? "Interfață clasică" : "Interfață ghidată"}</Btn>
                <Btn variant="secondary" onClick={() => remove(editId)}><Trash2 size={14} /> Șterge dosarul</Btn>
              </div>
            </div>
          </div> : <h2 className="text-lg font-bold mb-5">{editId ? "Editează înregistrarea" : cfg.addLabel}</h2>}
          {key === "prosumator" && editId && <SummaryStrip form={form} />}
          {key === "prosumator" && editId && hasUnsavedChanges && <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900" role="status" data-testid="unsaved-changes-warning">Modificări nesalvate — salvează cardurile modificate înainte să părăsești dosarul.</div>}
          {key === "prosumator" && editId && !guidedInterface && <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="dossier-quick-actions">
            {[
              ["schema", "Schema monofilară (PDF)", `/sld/${editId}/pdf?auth=${localStorage.getItem("den_token")}`],
              ["dossier", "Dosar prosumator (PDF)", `/docs/all/${editId}?auth=${localStorage.getItem("den_token")}`],
              ["pram", "Buletin PRAM", `/docs/buletin_priza/${editId}?auth=${localStorage.getItem("den_token")}`],
              ["pv", "PV probe", `/docs/pv_teste/${editId}?auth=${localStorage.getItem("den_token")}`],
            ].map(([id, label, path]) => <a key={id} href={`${API}${path}`} target="_blank" rel="noopener noreferrer" className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid={`dossier-quick-${id}`}>{label}</a>)}
            <button type="button" onClick={() => document.getElementById("dossier-section-equipment")?.scrollIntoView({ behavior: "smooth", block: "start" })} className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="dossier-quick-equipment">Echipamente</button>
            <button type="button" onClick={() => document.getElementById("dossier-section-documents")?.scrollIntoView({ behavior: "smooth", block: "start" })} className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="dossier-quick-documents">Acte & semnare</button>
          </div>}
          {key === "prosumator" && editId && guidedInterface && <section className="rounded-xl border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid="guided-dossier-steps">
            {(() => {
              const inverterRows = form.cef?.inverters || [];
              const missing = guidedStep === 0 ? [
                ["Client", !form.client_name], ["adresa locului de consum", !form.address], ["județul", !form.county], ["localitatea", !form.locality], ["tipul cererii", !form.request_type],
              ] : [];
              if (guidedStep === 1 && !inverterRows.some((inv) => inv.brand_model || inv.catalog_id)) missing.push(["invertorul și panourile din CEF", true]);
              if (guidedStep === 2 && !form.executant_rep) missing.push(["reprezentantul executantului", true]);
              if (guidedStep === 3 && form.status === "CER") missing.push(["generează dosarul PDF complet pentru trecerea la depunere", true]);
              if (guidedStep === 5 && !form.pif_no) missing.push(["datele PV de teste și punere în funcțiune", true]);
              const stepMissing = missing.filter(([_, absent]) => absent).map(([label]) => label);
              return <>
                <div className="mb-2 flex items-center justify-between gap-2"><b className="text-sm">Pasul {guidedStep + 1} din {GUIDED_STEPS.length}: {GUIDED_STEPS[guidedStep][1]}</b><span className="text-[11px]" style={{ color: "var(--muted)" }}>Poți schimba interfața oricând.</span></div>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                  {GUIDED_STEPS.map((step, index) => <button key={step[0]} type="button" onClick={() => jumpGuided(index)} className="rounded-lg border px-2 py-2 text-[10px] font-semibold" style={guidedStep === index ? { background: "#edf7f0", color: "var(--green)", borderColor: "var(--green)" } : { color: "var(--muted)", borderColor: "var(--line)" }} data-testid={`guided-step-${index + 1}`}>{index + 1}. {step[1]}</button>)}
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><span className="text-xs" style={{ color: stepMissing.length ? "#9a5c12" : "var(--green)" }} data-testid="guided-step-missing">{stepMissing.length ? `De completat: ${stepMissing.join(", ")}` : "Nu sunt date obligatorii lipsă în acest pas."}</span><div className="flex gap-2"><Btn variant="secondary" disabled={guidedStep === 0} onClick={() => jumpGuided(guidedStep - 1)}>Înapoi</Btn><Btn disabled={guidedStep === GUIDED_STEPS.length - 1} onClick={() => jumpGuided(guidedStep + 1)}>Pasul următor</Btn></div></div>
              </>;
            })()}
          </section>}
          {key === "prosumator" && editId && !guidedInterface && <nav className="sticky top-[54px] z-20 -mx-1 flex gap-2 overflow-x-auto bg-[#f8f6f1]/95 px-1 pb-2 pt-1 backdrop-blur md:top-0" aria-label="Navigare în dosar">
            {[ ["all", "Dosar complet", "dossier-top"], ["client", "Client", "dossier-section-client"], ["location", "Loc de consum", "dossier-section-location"], ["request", "Cererea", "dossier-section-request"], ["installation", "Branșament", "dossier-section-connection"], ["equipment", "Echipamente", "dossier-section-equipment"], ["topology", "Tablouri & schemă", "dossier-section-equipment"], ["pram", "PRAM", "dossier-section-pram"], ["pif", "Teste și PIF", "dossier-section-pif-tools"], ["documents", "Acte & semnare", "dossier-section-documents"], ["team", "Echipă", "dossier-section-team"], ["other", "Mesaje", "dossier-section-messages"], ["timeline", "Jurnal", "dossier-section-timeline"] ].map(([id, label, target]) => <button key={id} type="button" aria-current={dossierPage === id ? "location" : undefined} onClick={() => { setDossierPage(id); document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" }); }} className="shrink-0 rounded-lg border px-3 py-2 text-xs font-bold" style={dossierPage === id ? { background: "var(--navy)", color: "white", borderColor: "var(--navy)" } : { background: "#fffefa", color: "var(--muted)", borderColor: "var(--line)" }} data-testid={`dossier-page-${id}`}>{label}</button>)}
          </nav>}
          {key === "prosumator" && editId && showGuidedStep(0) && <DossierFieldSections id={editId} fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} baselineForm={baselineForm} saveErrors={saveErrors} sectionLabels={guidedInterface ? ["Client & date de identitate", "Loc de consum", "Cererea"] : ["Date dosar", "Client & date de identitate", "Loc de consum", "Cererea", "Branșament & măsură", "Date tehnice"]} />}
          {key === "prosumator" && !editId ? <div className="grid sm:grid-cols-2 gap-4" data-testid="new-dossier-simple-step">
            {prosumStep === 1 && <>
              {!newProsumClient && <div className="sm:col-span-2" data-testid="prosum-client-existing"><Field f={{ ...cfg.fields.find((field) => field.name === "client_name"), label: "Client existent" }} value={form.client_name} onChange={setVal} refOptions={refOptions} /></div>}
              <label className="sm:col-span-2 flex items-center gap-2 text-sm" data-testid="prosum-client-mode"><input type="checkbox" checked={newProsumClient} onChange={(e) => { const checked = e.target.checked; setNewProsumClient(checked); if (checked) setForm((current) => ({ ...current, client_name: "", kind: current.kind || "Persoană fizică" })); }} /> Client nou (nu există în listă)</label>
              {newProsumClient && <>
                <div className="sm:col-span-2 grid grid-cols-2 gap-2 rounded-xl p-1" style={{ background: "var(--bg)" }} data-testid="prosum-client-kind">
                  {["Persoană fizică", "Persoană juridică"].map((kind) => <button key={kind} type="button" onClick={() => setVal("kind", kind)} className="rounded-lg border px-3 py-2 text-xs font-bold" style={form.kind === kind ? { background: "white", color: "var(--green)", borderColor: "var(--line)", boxShadow: "0 1px 3px #00000010" } : { color: "var(--muted)", borderColor: "transparent" }}>{kind}</button>)}
                </div>
                {form.kind === "Persoană fizică" ? <>
                  <div className="sm:col-span-2 rounded-lg border border-dashed px-3 py-2" style={{ borderColor: "var(--line)", background: "#fffefa" }}>
                    <AiImportButton label="Scanează CI (poză sau PDF)" disabled={!form.allow_id_scan} onExtracted={(data) => {
                      const parts = String(data.client_name || "").trim().split(/\s+/).filter(Boolean);
                      setForm((current) => ({ ...current, ...data, client_name: "", new_client_last_name: parts[0] || current.new_client_last_name || "", new_client_first_name: parts.slice(1).join(" ") || current.new_client_first_name || "", kind: "Persoană fizică", files: [...(current.files || []), ...(data.file ? [data.file] : [])] }));
                    }} />
                    <label className="mt-2 flex items-start gap-2 text-[11px]" style={{ color: "var(--muted)" }}><input type="checkbox" checked={!!form.allow_id_scan} onChange={(e) => setVal("allow_id_scan", e.target.checked)} /> Sunt de acord ca poza/PDF-ul CI să fie trimis(ă) către serviciul AI configurat în DNS Energy pentru extragerea numelui și CNP-ului.</label>
                  </div>
                  <Field f={{ name: "new_client_last_name", label: "Nume", type: "text" }} value={form.new_client_last_name} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "new_client_first_name", label: "Prenume", type: "text" }} value={form.new_client_first_name} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "cnp", label: "CNP", type: "text" }} value={form.cnp} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "phone", label: "Telefon", type: "text" }} value={form.phone} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "hq_address", label: "Domiciliu (din CI)", type: "text", full: true }} value={form.hq_address} onChange={setVal} refOptions={refOptions} />
                </> : <>
                  <Field f={{ name: "new_company_name", label: "Denumire firmă", type: "text", full: true }} value={form.new_company_name} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "cnp", label: "CUI", type: "text" }} value={form.cnp} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "regcom", label: "Nr. Reg. Com.", type: "text" }} value={form.regcom} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "rep_name", label: "Administrator", type: "text" }} value={form.rep_name} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "phone", label: "Telefon", type: "text" }} value={form.phone} onChange={setVal} refOptions={refOptions} />
                  <Field f={{ name: "hq_address", label: "Sediu social", type: "text", full: true }} value={form.hq_address} onChange={setVal} refOptions={refOptions} />
                </>}
                <Field f={{ name: "email", label: "Email", type: "text" }} value={form.email} onChange={setVal} refOptions={refOptions} />
                <Field f={{ name: "bank", label: "Bancă", type: "text", placeholder: "pentru regularizarea de prosumator" }} value={form.bank} onChange={setVal} refOptions={refOptions} />
                <Field f={{ name: "iban", label: "IBAN", type: "text", full: true }} value={form.iban} onChange={setVal} refOptions={refOptions} />
              </>}
            </>}
            {prosumStep === 2 && <>
              <div className="sm:col-span-2 flex flex-wrap items-center gap-2" data-testid="prosum-location-mode">
                <button type="button" onClick={() => setNewProsumLocation(false)} disabled={!knownLocations.length} className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-40" style={!newProsumLocation ? { background: "var(--green)", color: "white", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Loc de consum existent</button>
                <button type="button" onClick={() => setNewProsumLocation(true)} className="rounded-lg border px-3 py-2 text-xs font-bold" style={newProsumLocation ? { background: "var(--green)", color: "white", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Loc de consum nou</button>
                {!knownLocations.length && <span className="text-xs" style={{ color: "var(--muted)" }}>Nu există încă o locație salvată pentru acest client.</span>}
              </div>
              {!newProsumLocation && <div className="den-field sm:col-span-2"><label>Alege locul de consum</label><select className="den-input" value={form._location_key || knownLocations.find((location) => location.address === form.address && location.county === form.county && location.locality === form.locality && location.pod === form.pod)?.id || ""} onChange={(e) => {
                const found = knownLocations.find((location) => location.id === e.target.value);
                if (found) setForm((current) => ({ ...current, ...Object.fromEntries(LOCATION_FIELDS.map((field) => [field, found[field]])), _location_key: found.id }));
              }} data-testid="existing-location-select"><option value="">Alege locul de consum...</option>{knownLocations.map((location) => <option key={location.id} value={location.id}>{[location.address, location.locality, location.county, location.pod && `POD ${location.pod}`].filter(Boolean).join(" · ")}</option>)}</select></div>}
              {newProsumLocation && <>
                <Field f={cfg.fields.find((field) => field.name === "address")} value={form.address} onChange={setVal} refOptions={refOptions} />
                <SameAddress form={form} setVal={setVal} />
                <div className="den-field"><label htmlFor="new-dossier-county">Județ *</label><select id="new-dossier-county" className="den-input" value={form.county || ""} onChange={(e) => setVal("county", e.target.value)} data-testid="new-dossier-county"><option value="">Alege județul</option>{form.county && !RO_COUNTIES.includes(form.county) && <option value={form.county}>{form.county}</option>}{RO_COUNTIES.map((county) => <option key={county}>{county}</option>)}</select></div>
                <Field f={cfg.fields.find((field) => field.name === "locality")} value={form.locality} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "postal_code")} value={form.postal_code} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "pod")} value={form.pod} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "operator")} value={form.operator} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "location_code")} value={form.location_code} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "supplier")} value={form.supplier} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "approved_kva")} value={form.approved_kva} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "existing_supply")} value={form.existing_supply} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "cf_nr")} value={form.cf_nr} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "cadastral_nr")} value={form.cadastral_nr} onChange={setVal} refOptions={refOptions} />
                <Field f={cfg.fields.find((field) => field.name === "location_new")} value={form.location_new} onChange={setVal} refOptions={refOptions} />
              </>}
              <div className="sm:col-span-2 rounded-lg px-3 py-2 text-xs" style={{ background: "var(--bg)", color: "var(--muted)" }}>Datele cunoscute despre client și locul de consum se preiau din dosarele existente. Pentru POD, codul locului și puterea aprobată, folosește factura sau ATR-ul. Echipamentele se completează după creare.</div>
            </>}
            {prosumStep === 3 && <>
              <div className="sm:col-span-2"><Field f={cfg.fields.find((field) => field.name === "request_type")} value={form.request_type} onChange={setVal} refOptions={refOptions} /></div>
              <Field f={cfg.fields.find((field) => field.name === "supply")} value={form.supply} onChange={setVal} refOptions={refOptions} />
              <Field f={cfg.fields.find((field) => field.name === "date")} value={form.date} onChange={setVal} refOptions={refOptions} />
              <label className="sm:col-span-2 flex items-center gap-2 rounded-lg border px-3 py-3 text-sm" style={{ borderColor: "var(--line)" }}><input type="checkbox" checked={form.afm === "Da"} onChange={(e) => setVal("afm", e.target.checked ? "Da" : "Nu")} data-testid="new-dossier-afm" /> Finanțare AFM (Casa Verde)</label>
              <div className="sm:col-span-2 rounded-lg px-3 py-2 text-xs" style={{ background: "var(--bg)", color: "var(--muted)" }}>Invertorul, panourile, stringurile și bateria se aleg în dosar. Documentele și schema se generează din datele completate și se verifică înainte de semnare.</div>
            </>}
          </div> : <div className="grid sm:grid-cols-2 gap-4">
            {cfg.fields.map((f, i) => {
              return <Field key={f.name || `s${i}`} f={f} value={form[f.name]} onChange={setVal} refOptions={refOptions} allowNewReference={key === "prosumator" && f.name === "client_name"} ai={can(user, "ai_gpt") ? { module: key, form } : null} />;
            })}
          </div>}

          {key === "prosumator" && editId && showGuidedStep(1) && <DossierFieldSections id={editId} fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} baselineForm={baselineForm} saveErrors={saveErrors} sectionLabels={["Branșament & măsură"]} />}
          {key === "prosumator" && editId && showGuidedStep(1) && <div id="dossier-section-equipment" className="scroll-mt-24">
            <QuickEquipment form={form} catalog={equipmentCatalog} onChange={(patch) => setForm((current) => ({ ...current, ...patch }))} onSave={() => saveDossierSection("Echipamente")} isDirty={JSON.stringify(form.cef || {}) !== JSON.stringify(baselineForm?.cef || {})} saveError={saveErrors.Echipamente} />
          </div>}
          {key === "prosumator" && editId && showGuidedStep(1) && <div id="dossier-section-topology" className="scroll-mt-24">
            <section className="den-panel !p-0 overflow-hidden" data-testid="installation-panel-boards">
              <div className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5" style={{ borderColor: "var(--line)" }}>
                <div className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: JSON.stringify(form.cef || {}) !== JSON.stringify(baselineForm?.cef || {}) ? "#e98a22" : "var(--green)" }} /><h3 className="font-bold text-sm">Topologie, protecții & TEG</h3>{JSON.stringify(form.cef || {}) !== JSON.stringify(baselineForm?.cef || {}) && <span className="text-[10px] font-bold text-amber-700">Modificări nesalvate</span>}</div>
                <button type="button" onClick={() => saveDossierSection("Topologie & schemă")} className="shrink-0 rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button>
              </div>
              {saveErrors["Topologie & schemă"] && <p className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800" role="alert">Salvarea a eșuat: {saveErrors["Topologie & schemă"]}</p>}
              <div className="p-4 sm:p-5"><CefEditor value={form.cef} onChange={(v) => setVal("cef", v)} groundingOhm={form.grounding_ohm} groundingLimit={form.grounding_limit} boardsOnly /><SldPanel id={editId} form={form} setVal={setVal} /></div>
            </section>
          </div>}
          {key === "prosumator" && editId && showGuidedStep(1) && <details className="den-panel !p-0 overflow-hidden" data-testid="technical-manual-overrides"><summary className="cursor-pointer px-4 py-3 text-sm font-bold">Date tehnice suplimentare (opțional)</summary><div className="p-4 sm:p-5"><DossierFieldSections id={editId} fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} baselineForm={baselineForm} saveErrors={saveErrors} sectionLabels={["Date tehnice"]} /></div></details>}
          {key === "prosumator" && editId && showGuidedStep(2) && <DossierFieldSections id={editId} fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} baselineForm={baselineForm} saveErrors={saveErrors} sectionLabels={["Date documente dosar"]} />}
          {key === "prosumator" && editId && showGuidedStep(5) && <DossierFieldSections id={editId} fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} baselineForm={baselineForm} saveErrors={saveErrors} sectionLabels={["Buletin priză de pământ (valori măsurate)", "Punere în funcțiune și teste", "Recepție la terminarea lucrărilor"]} />}
          {key === "prosumator" && editId && showGuidedStep(5) && <div id="dossier-section-pif-tools" className="scroll-mt-24"><section className="den-panel !p-0 overflow-hidden"><div className="mb-0 flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5"><h3 className="font-bold text-sm">PV Teste — probe / punere sub tensiune</h3><button type="button" onClick={() => saveDossierSection("Teste și PIF")} className="rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button></div>{saveErrors["Teste și PIF"] && <p className="mx-4 mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800" role="alert">Salvarea a eșuat: {saveErrors["Teste și PIF"]}</p>}<div className="p-4 sm:p-5"><DossierExtras form={form} setVal={setVal} view="pif" /><PifPanel id={editId} /></div></section></div>}

          {key === "prosumator" && !editId && <div className="flex items-center justify-between gap-2 mt-6 border-t pt-4" style={{ borderColor: "var(--line)" }}>
            <div className="flex gap-2"><Btn variant="secondary" onClick={() => setForm(null)}>Renunță</Btn>{prosumStep > 1 && <Btn variant="secondary" onClick={() => setProsumStep((s) => s - 1)}>Înapoi</Btn>}</div>
            {prosumStep < 3 ? <Btn onClick={continueProsum}>Continuă</Btn> : <Btn onClick={save} data-testid="save-btn"><Plus size={15} /> Creează dosarul</Btn>}
          </div>}

          {cfg.checklist && (key !== "prosumator" || !!editId) && (
            <div className="mt-6 scroll-mt-24" id={key === "prosumator" ? "dossier-section-checklist" : undefined}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-sm">Checklist documente — {cfg.title}</h3>
                <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#eef4ff", color: "var(--blue)" }}>{checkedCount} / {cfg.checklist.length} bifate</span>
              </div>
              <div className="grid sm:grid-cols-2 gap-2">
                {cfg.checklist.map((c) => (
                  <label key={c} className="flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer text-sm" style={{ borderColor: "var(--line)" }}>
                    <input type="checkbox" checked={!!checks[c]} onChange={(e) => setChecks((p) => ({ ...p, [c]: e.target.checked }))} data-testid={`check-${c}`} />
                    <span>{c}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {key === "prosumator" && editId && showGuidedStep(2) && <div id="dossier-section-team" className="mt-6 scroll-mt-24"><div className="flex items-center justify-between gap-3"><h3 className="font-bold text-base">Echipă & semnături</h3><button type="button" onClick={() => saveDossierSection("Echipă & semnături")} className="rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button></div>{saveErrors["Echipă & semnături"] && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800" role="alert">Salvarea a eșuat: {saveErrors["Echipă & semnături"]}</p>}<DossierExtras form={form} setVal={setVal} view="team" /></div>}
          {key === "prosumator" && editId && showGuidedStep(2) && <div id="dossier-section-documents" className="scroll-mt-24"><DossierOpis id={editId} refreshKey={`${form.pram_mode || "self"}-${form.opis?.priza?.upload?.original_filename || ""}`} /></div>}
          {key === "prosumator" && editId && showGuidedStep(3) && <div id="generated-docs" className="scroll-mt-24"><GeneratedDocs id={editId} files={form.files} /><SignRequests dossierId={editId} /></div>}
          {key === "prosumator" && editId && showGuidedStep(4) && <div id="dossier-section-messages" className="mt-6 space-y-4 scroll-mt-24"><AssignBox value={form.assigned_to} onChange={(v) => setVal("assigned_to", v)} /><DossierMessages id={editId} /><SimpleDossierBtn id={editId} /><AiDossierCheck id={editId} /><div id="dossier-section-timeline" className="scroll-mt-24"><DossierTimeline id={editId} /></div></div>}
          {key === "power" && <PowerDossier id={editId} form={form} setVal={setVal} />}
          {key === "atr" && <AtrDossier id={editId} form={form} setVal={setVal} />}
          {key === "diu" && editId && <DiuDossier id={editId} form={form} setVal={setVal} setForm={setForm} savedAt={savedAt} />}
          {key === "diu" && editId && <SignRequests dossierId={editId} module="diu" />}
          {key === "diu" && editId && <AiPrecheck id={editId} base="diu" open={diuPre} onClose={() => setDiuPre(false)} onFinalize={doSave} form={form}
            title="Verificare AI înainte de predarea către beneficiar" action="Salvează ca „Predat beneficiarului”" />}
          {key === "clients" && editId && <ClientDocs client={form} onChange={(docs) => setVal("docs", docs)} />}
          {key === "clients" && editId && <SignRequests clientName={form.name} />}

          {!(key === "prosumator" && !editId) && <div className={`flex gap-2 mt-6 den-noprint ${key === "prosumator" && editId ? "sticky bottom-2 z-20 rounded-xl border bg-white/95 p-3 shadow-lg backdrop-blur" : ""}`} style={key === "prosumator" && editId ? { borderColor: "var(--line)" } : undefined}>
            {key === "prosumator" && editId && <Btn variant="secondary" className="md:hidden" onClick={() => jumpGuided(4)} data-testid="mobile-od-messages">Mesaje OD</Btn>}
            <Btn onClick={save} data-testid="save-btn">Salvează</Btn>
            <Btn variant="secondary" onClick={() => window.print()} data-testid="pdf-btn">Tipărește / PDF</Btn>
            <Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>
          </div>}
        </div>
      )}

      <div className="den-panel">
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <div><h2 className="text-lg font-bold">Dosare {key === "prosumator" ? (archiveView ? "arhivate" : "active") : "salvate"} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({filtered.length})</span></h2>{key === "prosumator" && <p className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>{archiveView ? "Fără activitate în ultimele 6 luni; la actualizare revin la dosarele active." : "Dosarele fără activitate timp de 6 luni se arhivează automat."}</p>}</div>
          <div className="flex flex-wrap items-center gap-2">
          {key === "prosumator" && <div className="flex rounded-lg border p-1" style={{ borderColor: "var(--line)" }}>
            <button onClick={() => setArchiveView(false)} className={`rounded-md px-3 py-2 text-[11px] font-bold ${!archiveView ? "text-white" : ""}`} style={!archiveView ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-active-dossiers">Active ({items.length - archiveCount})</button>
            <button onClick={() => setArchiveView(true)} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${archiveView ? "text-white" : ""}`} style={archiveView ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-archived-dossiers"><Archive size={13} /> Arhivate ({archiveCount})</button>
          </div>}
          {key === "prosumator" && <div className="flex rounded-lg border p-1" style={{ borderColor: "var(--line)" }}>
            <button onClick={() => setDossierView("kanban")} className={`hidden md:inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${dossierView === "kanban" ? "text-white" : ""}`} style={dossierView === "kanban" ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-kanban"><LayoutGrid size={14} /> Kanban</button>
            <button onClick={() => setDossierView("list")} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${mobileDossierList || dossierView === "list" ? "text-white" : ""}`} style={mobileDossierList || dossierView === "list" ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-list"><List size={14} /> Listă</button>
          </div>}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input data-testid="search-input" className="den-input w-[240px]" style={{ paddingLeft: 34 }} placeholder="Caută..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          </div>
        </div>

        {key === "prosumator" && <div className="mb-4 flex flex-wrap items-end gap-2 rounded-xl p-3" style={{ background: "var(--bg)" }} data-testid="dossier-filters">
          <span className="mr-1 inline-flex items-center gap-1.5 self-center text-[11px] font-bold" style={{ color: "var(--muted)" }}><Filter size={14} /> Filtre</span>
          {[["Operator", "operator", operatorFilter, setOperatorFilter], ["Județ", "county", countyFilter, setCountyFilter], ["Localitate", "locality", localityFilter, setLocalityFilter]].map(([label, field, value, set]) => <label key={field} className="den-field min-w-[150px] flex-1"><span className="sr-only">{label}</span><select className="den-input !py-2" value={value} onChange={(e) => set(e.target.value)} aria-label={label}><option value="">Toate — {label.toLowerCase()}</option>{optionValues(field).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>)}
          <label className="den-field min-w-[170px] flex-1"><span className="sr-only">Client</span><input className="den-input !py-2" value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} placeholder="Client…" aria-label="Client" data-testid="filter-client" /></label>
          {(operatorFilter || countyFilter || localityFilter || clientFilter) && <button className="px-2 py-2 text-[11px] font-bold" style={{ color: "var(--blue)" }} onClick={() => { setOperatorFilter(""); setCountyFilter(""); setLocalityFilter(""); setClientFilter(""); }}>Șterge filtrele</button>}
          <span className="ml-auto self-center text-[11px]" style={{ color: "var(--muted)" }}>{filtered.length} / {items.length} dosare</span>
        </div>}

        {filtered.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>{archiveView ? "Nu există dosare arhivate." : (items.length ? "Nu există dosare care să corespundă filtrelor." : "Nu există înregistrări încă.")}</div>
        ) : key === "prosumator" && !mobileDossierList && dossierView === "kanban" ? (
          <div className="flex gap-3 overflow-x-auto pb-3" data-testid="dossier-kanban">
            {statusOptions.map((status) => {
              const cards = filtered.filter((item) => displayStatus(item) === status);
              return <section key={status} className="w-[260px] shrink-0 rounded-xl p-3" style={{ background: "#f5f7fb" }} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const item = items.find((i) => i.id === dragId(e)); if (item && item.status !== status) changeStatus(item, status); }} data-testid={`kanban-column-${status}`}>
                <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-[10px] font-extrabold uppercase tracking-wide">{status}</h3><span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "#e8edf5", color: "var(--muted)" }}>{cards.length}</span></div>
                <div className="space-y-2 min-h-10">{cards.map((item) => <article key={item.id} draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", item.id)} className="rounded-xl border bg-white p-3 shadow-sm cursor-grab" style={{ borderColor: item.blocker?.active ? "#e8a1a1" : "var(--line)" }} data-testid={`kanban-card-${item.id}`}>
                  <button className="w-full text-left" onClick={() => openEdit(item)}><span className="block text-[10px] font-bold" style={{ color: "var(--blue)" }}>{item.number || "Fără număr"}</span><b className="mt-1 block text-[12px]">{item.client_name || "Beneficiar neprecizat"}</b><span className="mt-1 block truncate text-[10px]" style={{ color: "var(--muted)" }}>{[item.locality, item.county].filter(Boolean).join(", ") || item.address || "Loc de consum necompletat"}</span>{item.blocker?.active && <span className="mt-2 block rounded-md px-2 py-1 text-[10px] font-semibold" style={{ color: "#9b2c2c", background: "#fff0f0" }}>Blocaj: {item.blocker.title}</span>}</button>
                  <div className="mt-2 flex items-center justify-between border-t pt-2" style={{ borderColor: "var(--line)" }}><span className="truncate text-[9px]" style={{ color: "var(--muted)" }}>{item.operator || "Operator neprecizat"}</span><button className="rounded-md p-1 hover:bg-slate-100" title="Editează dosarul" onClick={() => openEdit(item)}><ChevronRight size={14} /></button></div>
                </article>)}</div>
              </section>;
            })}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="items-table">
              <thead>
                <tr className="text-left" style={{ background: "#f8fafd", color: "var(--muted)" }}>
                  {cfg.columns.map((c) => <th key={c.key} className="px-3 py-2.5 font-semibold text-[12px] whitespace-nowrap">{c.label}</th>)}
                  <th className="px-3 py-2.5 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <tr key={it.id} className="border-t hover:bg-[#fafcff]" style={{ borderColor: "var(--line)" }}>
                    {cfg.columns.map((c) => <td key={c.key} className="px-3 py-3 whitespace-nowrap">{key === "prosumator" && c.key === "status" ? <span className="inline-flex items-center gap-2"><span className="rounded-full px-2.5 py-1 text-[11px] font-bold" style={{ background: "#eef4ff", color: "#1d4ed8" }}>{displayStatus(it)}</span>{it.blocker?.active && <span className="rounded-full px-2 py-1 text-[10px] font-bold" style={{ color: "#9b2c2c", background: "#fff0f0" }}>Blocaj</span>}</span> : it[c.key] || "—"}</td>)}
                    <td className="px-3 py-3 text-right whitespace-nowrap">
                      <button onClick={() => openEdit(it)} data-testid={`edit-${it.id}`} className="p-1.5 rounded hover:bg-[#eef4ff]" title="Editează"><Pencil size={15} style={{ color: "var(--blue)" }} /></button>
                      {canDelete && <button onClick={() => remove(it.id)} data-testid={`delete-${it.id}`} className="p-1.5 rounded hover:bg-[#fff0f0] ml-1" title="Șterge"><Trash2 size={15} style={{ color: "#b33333" }} /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


