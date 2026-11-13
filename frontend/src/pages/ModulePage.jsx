import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, API } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X, LayoutGrid, List, Filter, ChevronRight, Archive } from "lucide-react";
import { toast } from "sonner";
import { AiImportButton, GeneratedDocs } from "@/components/ProsumatorTools";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs } from "@/components/dossier/ClientDocs";
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
const RO_COUNTIES = ["Alba", "Arad", "Argeș", "Bacău", "Bihor", "Bistrița-Năsăud", "Botoșani", "Brăila", "Brașov", "București", "Buzău", "Călărași", "Caraș-Severin", "Cluj", "Constanța", "Covasna", "Dâmbovița", "Dolj", "Galați", "Giurgiu", "Gorj", "Harghita", "Hunedoara", "Ialomița", "Iași", "Ilfov", "Maramureș", "Mehedinți", "Mureș", "Neamț", "Olt", "Prahova", "Sălaj", "Satu Mare", "Sibiu", "Suceava", "Teleorman", "Timiș", "Tulcea", "Vâlcea", "Vaslui", "Vrancea"];
const LOCATION_FIELDS = ["address", "county", "locality", "postal_code", "pod", "operator", "location_code", "supplier", "approved_kva", "existing_supply", "location_new", "cadastral_nr", "cf_nr"];

function Field({ f, value, onChange, refOptions, ai, allowNewReference = false }) {
  if (f.type === "section") return <h3 className="sm:col-span-2 mt-3 pt-3 border-t text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h3>;
  const common = { className: "den-input", value: value ?? "", onChange: (e) => onChange(f.name, e.target.value), placeholder: f.placeholder || "", "data-testid": `field-${f.name}` };
  return (
    <div className={`den-field ${f.full ? "sm:col-span-2" : ""}`}>
      {f.type === "checkbox" ? <label className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm" style={{ borderColor: "var(--line)" }}><input type="checkbox" checked={!!value} onChange={(e) => onChange(f.name, e.target.checked)} data-testid={`field-${f.name}`} /><span>{f.label}</span></label> : <><label>{f.label}</label>
      {f.type === "textarea" ? (
        <><textarea {...common} rows={3} />{ai && <AiDraft module={ai.module} field={f.name} label={f.label} form={ai.form} onApply={onChange} />}</>
      ) : f.type === "select" ? (
        <select {...common}><option value="">Alege...</option>{value && !f.options.includes(value) && <option value={value}>{value}</option>}{f.options.map((o) => <option key={o} value={o}>{o}</option>)}</select>
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

function QuickEquipment({ form, catalog, onChange }) {
  const cef = form.cef || { grid: {}, inverters: [], shared_batteries: [] };
  const inv = cef.inverters?.[0] || {};
  const options = (category) => catalog.filter((item) => item.category === category);
  const byId = (id, category) => options(category).find((item) => item.id === id);
  const setInv = (patch, legacy = {}) => {
    const nextInv = { ...inv, ...patch };
    const nextCef = { ...cef, grid: { ...(cef.grid || {}), ...(form.supply ? { supply: form.supply } : {}) }, inverters: [nextInv, ...(cef.inverters || []).slice(1)] };
    const number = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
    const configured = nextCef.inverters.filter((item) => item.brand_model || item.catalog_id);
    const panelCount = configured.reduce((sum, item) => sum + (item.strings || []).reduce((n, string) => n + number(string.panels), 0), 0);
    const pvKwp = configured.reduce((sum, item) => sum + (item.strings || []).reduce((n, string) => n + number(string.panels) * number(item.panel_w) / 1000, 0), 0);
    const inverterKw = configured.reduce((sum, item) => sum + number(item.p_nom_kw) * Math.max(1, number(item.inverter_count) || 1), 0);
    const exportLimits = configured.map((item) => number(item.p_limit_kw)).filter((value) => value > 0);
    const power = pvKwp > 0 && inverterKw > 0 ? Math.min(pvKwp, inverterKw, ...exportLimits) : 0;
    const batteries = configured.filter((item) => item.battery_mode === "own");
    const batteryKwh = batteries.reduce((sum, item) => sum + number(item.battery?.kwh) * Math.max(1, number(item.battery?.modules) || 1), 0);
    onChange({
      cef: nextCef,
      panel_count: panelCount || "",
      _kwp: pvKwp || "",
      inverter_count: configured.length || "",
      inverter_kw: inverterKw || "",
      ...(power ? { power } : {}),
      battery_kwh: batteryKwh || "",
      system_type: batteryKwh ? "Hibrid cu baterie" : "On-grid",
      ...legacy,
    });
  };
  const chooseInverter = (id) => {
    const item = byId(id, "Invertor");
    if (!item) return;
    setInv({ catalog_id: item.id, brand_model: item.brand_model, type: item.type || "Hibrid", phases: item.phases || form.supply || "Trifazat",
      p_nom_kw: item.p_nom_kw, p_max_kw: item.p_max_kw || item.p_nom_kw, vdc_max: item.vdc_max, mppt_min: item.mppt_min,
      mppt_max: item.mppt_max, mppt_count: item.mppt_count || 1, imax_mppt: item.imax_mppt,
      ac: { cable_type: "RVK", material: "Cu", install: "C", section: 6, ...(inv.ac || {}) },
      dc: { cable_type: "H1Z2Z2-K", material: "Cu", section: 6, ...(inv.dc || {}) },
      strings: inv.strings || [], battery_mode: inv.battery_mode || "none" },
    { inverter: item.brand_model, inverter_kw: item.p_nom_kw || "", inverter_count: 1, supply: item.phases || form.supply || "Trifazat",
      system_type: inv.battery_mode === "own" || inv.battery_mode === "shared" ? "Hibrid cu baterie" : "On-grid", power: item.p_nom_kw || "" });
  };
  const choosePanel = (id) => {
    const item = byId(id, "Panou");
    if (!item) return;
    setInv({ panel_catalog_id: item.id, panel_model: item.brand_model, panel_w: item.w, panel_voc: item.voc,
      panel_vmp: item.vmp, panel_isc: item.isc, panel_coef_voc: item.coef_voc },
    { panels: item.brand_model, panel_w: item.w || "" });
  };
  const setStrings = (value) => {
    const old = inv.strings || [];
    const counts = value.split(",").map((part) => part.trim()).filter(Boolean);
    const mpptCount = Math.max(1, Number(inv.mppt_count) || 1);
    const strings = counts.map((part, i) => ({ ...(old[i] || {}), panels: Number(part) || "", mppt: old[i]?.mppt || (i % mpptCount) + 1 }));
    const count = strings.reduce((sum, item) => sum + (Number(item.panels) || 0), 0);
    setInv({ strings_text: value, strings }, { panel_count: count || "" });
  };
  const chooseBattery = (id) => {
    const item = byId(id, "Baterie");
    if (!item) {
      setInv({ battery_mode: "none", battery: undefined }, { battery: "", battery_kwh: "", battery_v: "", battery_ah: "", system_type: "On-grid" });
      return;
    }
    const modules = Math.max(1, Number(inv.battery?.modules) || 1);
    const battery = { ...(inv.battery || {}), catalog_id: item.id, model: item.brand_model, kwh: item.kwh,
      ah: item.ah, voltage: item.voltage, coupling: item.coupling || "DC", modules };
    setInv({ battery_mode: "own", battery }, { battery: item.brand_model, battery_kwh: (Number(item.kwh) || 0) * modules || "",
      battery_v: item.voltage || "", battery_ah: item.ah || "", system_type: "Hibrid cu baterie" });
  };
  const setBatteryModules = (value) => {
    const modules = Math.max(1, Number(value) || 1);
    const battery = { ...(inv.battery || {}), modules };
    setInv({ battery }, { battery_kwh: (Number(battery.kwh) || 0) * modules || "" });
  };
  const selectedBatteryId = inv.battery_mode === "own" ? (inv.battery?.catalog_id || "manual") : "none";
  return <section className="sm:col-span-2 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="new-dossier-equipment">
    <div className="mb-3"><h3 className="font-bold text-base">Instalație fotovoltaică</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Alegi invertorul, panoul, stringurile și bateria dacă există. Catalogul completează datele tehnice; puterea CEF și totalurile se calculează din echipamentele alese. Verifică valorile propuse în dosar înainte de generarea documentelor.</p></div>
    <div className="grid gap-3 sm:grid-cols-2">
      <F label="Invertor · model și putere" value={inv.catalog_id || (inv.brand_model ? "manual" : "")} options={[["manual", "Introduc manual modelul"], ...options("Invertor").map((item) => [item.id, `${item.brand_model} · ${item.p_nom_kw ?? "—"} kW`])]} onChange={(id) => {
        if (id === "manual") setInv({ catalog_id: "", brand_model: inv.brand_model || "", p_nom_kw: inv.p_nom_kw || "" }); else chooseInverter(id);
      }} testid="quick-inverter" />
      {(!inv.catalog_id || inv.catalog_id === "manual") && <><F label="Model invertor" value={inv.brand_model} onChange={(v) => setInv({ brand_model: v }, { inverter: v })} testid="quick-inverter-model" /><F label="Putere invertor (kW)" type="number" value={inv.p_nom_kw} onChange={(v) => setInv({ p_nom_kw: v }, { inverter_kw: v, power: v })} testid="quick-inverter-power" /></>}
      {inv.catalog_id && <div className="rounded-lg px-3 py-2 text-xs self-end" style={{ background: "#edf7f0", color: "var(--green)" }}>Putere preluată din catalog: <b>{inv.p_nom_kw || "—"} kW</b></div>}
      <F label="Panou · model și putere" value={inv.panel_catalog_id || (inv.panel_model ? "manual" : "")} options={[["manual", "Introduc manual modelul"], ...options("Panou").map((item) => [item.id, `${item.brand_model} · ${item.w ?? "—"} W`])]} onChange={(id) => {
        if (id === "manual") setInv({ panel_catalog_id: "", panel_model: inv.panel_model || "", panel_w: inv.panel_w || "" }); else choosePanel(id);
      }} testid="quick-panel" />
      {(!inv.panel_catalog_id || inv.panel_catalog_id === "manual") && <><F label="Model panou" value={inv.panel_model} onChange={(v) => setInv({ panel_model: v }, { panels: v })} testid="quick-panel-model" /><F label="Putere panou (W)" type="number" value={inv.panel_w} onChange={(v) => setInv({ panel_w: v }, { panel_w: v })} testid="quick-panel-power" /></>}
      {inv.panel_catalog_id && <div className="rounded-lg px-3 py-2 text-xs self-end" style={{ background: "#edf7f0", color: "var(--green)" }}>Putere preluată din catalog: <b>{inv.panel_w || "—"} W</b></div>}
      <div className="sm:col-span-2"><F label="Panouri pe stringuri (ex.: 12, 12)" value={inv.strings_text ?? (inv.strings || []).map((item) => item.panels).filter(Boolean).join(", ")} onChange={setStrings} testid="quick-strings" /><p className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>Un număr pentru fiecare string; distribuția pe MPPT se face automat.</p></div>
      <F label="Baterie" value={selectedBatteryId} options={[["none", "Fără baterie"], ["manual", "Baterie introdusă manual"], ...options("Baterie").map((item) => [item.id, `${item.brand_model} · ${item.kwh ?? "—"} kWh`])]} onChange={(id) => {
        if (id === "none") chooseBattery("");
        else if (id === "manual") setInv({ battery_mode: "own", battery: { ...(inv.battery || {}), modules: inv.battery?.modules || 1 } }, { system_type: "Hibrid cu baterie" });
        else chooseBattery(id);
      }} testid="quick-battery" />
      {selectedBatteryId !== "none" && <>
        {selectedBatteryId === "manual" && <><F label="Model baterie" value={inv.battery?.model} onChange={(v) => setInv({ battery: { ...(inv.battery || {}), model: v } }, { battery: v })} testid="quick-battery-model" /><F label="Capacitate (kWh/modul)" type="number" value={inv.battery?.kwh} onChange={(v) => setInv({ battery: { ...(inv.battery || {}), kwh: v } }, { battery_kwh: (Number(v) || 0) * Math.max(1, Number(inv.battery?.modules) || 1) })} testid="quick-battery-power" /></>}
        <F label="Număr unități baterie" type="number" value={inv.battery?.modules || 1} onChange={setBatteryModules} testid="quick-battery-units" />
      </>}
    </div>
    {inv.strings?.length > 0 && <div className="mt-3 text-xs font-semibold" style={{ color: "var(--green)" }}>Total automat: {inv.strings.reduce((sum, item) => sum + (Number(item.panels) || 0), 0)} panouri · {(inv.strings.reduce((sum, item) => sum + (Number(item.panels) || 0), 0) * (Number(inv.panel_w) || 0) / 1000).toFixed(2)} kWp</div>}
  </section>;
}

function DossierFieldSections({ fields, form, setVal, refOptions, ai, onSaveSection }) {
  const sections = [];
  let current = { label: "Date dosar", fields: [] };
  fields.forEach((field) => {
    if (field.type === "section") {
      if (current.fields.length) sections.push(current);
      current = { label: field.label, fields: [] };
    } else current.fields.push(field);
  });
  if (current.fields.length) sections.push(current);

  const equipmentFields = new Set(["inverter", "inverter_kw", "inverter_count", "panels", "panel_count", "panel_w", "battery", "battery_kwh", "battery_v", "battery_ah"]);
  return <div className="space-y-4" data-testid="dossier-section-cards">
    {sections.map((section) => {
      const visibleFields = section.label === "Date tehnice" ? section.fields.filter((field) => !equipmentFields.has(field.name)) : section.fields;
      if (!visibleFields.length) return null;
      const sectionId = ({ Client: "dossier-section-client", "Client & date de identitate": "dossier-section-client", "Loc de consum": "dossier-section-location", Cererea: "dossier-section-request", "Date tehnice": "dossier-section-installation", "Date documente dosar": "dossier-section-documents-data", "Recepție la terminarea lucrărilor": "dossier-section-reception", "Punere în funcțiune și teste": "dossier-section-pif", "Buletin priză de pământ (valori măsurate)": "dossier-section-pram", "Tablou general și alimentare": "dossier-section-panel", "Recepție, punere în funcțiune și garanție": "dossier-section-warranty" })[section.label] || `dossier-section-${section.label.toLocaleLowerCase("ro").replace(/[^a-z0-9]+/g, "-")}`;
      return (
      <section key={section.label} id={sectionId} className="den-panel !p-0 overflow-hidden scroll-mt-24" data-testid={`dossier-section-${section.label}`}>
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5" style={{ borderColor: "var(--line)" }}>
          <div className="flex min-w-0 items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--green)" }} aria-hidden="true" />
          <h3 className="text-sm font-bold">{section.label}</h3>
          </div>
          {section.label === "Loc de consum" && form.pod && <span className="min-w-0 truncate text-xs" style={{ color: "var(--muted)" }}>{form.pod}</span>}
          <button type="button" onClick={() => onSaveSection(section.label)} className="shrink-0 rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }} data-testid={`save-section-${sectionId}`}>Salvează</button>
        </div>
        <div className="grid sm:grid-cols-2 gap-4 p-4 sm:p-5">
          {visibleFields.map((field) => <div key={field.name} className={field.full ? "sm:col-span-2" : ""}><Field f={field} value={form[field.name]} onChange={setVal} refOptions={refOptions} ai={ai} />{section.label === "Loc de consum" && field.name === "address" && <div className="mt-2"><SameAddress form={form} setVal={setVal} /></div>}</div>)}
          {section.label === "Cererea" && <RequestLoads form={form} setVal={setVal} />}
        </div>
      </section>
      );
    })}
  </div>;
}

function SummaryStrip({ form }) {
  const inverters = form.cef?.inverters || [];
  const asNumber = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
  const cefPanels = inverters.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, s) => n + asNumber(s.panels), 0), 0);
  const cefKwp = inverters.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, s) => n + asNumber(s.panels) * asNumber(inv.panel_w) / 1000, 0), 0);
  const cefExport = inverters.reduce((sum, inv) => sum + asNumber(inv.p_limit_kw || inv.p_nom_kw), 0);
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
  const [operatorFilter, setOperatorFilter] = useState("");
  const [countyFilter, setCountyFilter] = useState("");
  const [localityFilter, setLocalityFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [archiveView, setArchiveView] = useState(false);

  const load = () => api.get(`/data/${key}`).then((r) => {
    setItems(r.data);
    const eid = new URLSearchParams(window.location.search).get("edit");
    const it = eid && r.data.find((x) => x.id === eid);
    if (it) { setForm({ ...it }); setEditId(it.id); setChecks(it.checklist || {}); window.history.replaceState(null, "", window.location.pathname); }
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

  const openNew = () => { const today = new Date().toISOString().slice(0, 10); setForm(key === "prosumator" ? { date: today, doc_date: today, status: "CER", kind: "Persoană fizică", request_type: "Fără spor de putere", afm: "Nu", location_new: false } : {}); setEditId(null); setChecks({}); setProsumStep(1); setNewProsumClient(false); setNewProsumLocation(true); setDossierPage("all"); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); setProsumStep(1); setDossierPage("all"); };
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
      if (editId) await api.put(`/data/${key}/${editId}`, payload);
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
        setForm(dossier); setEditId(dossier.id); setChecks(dossier.checklist || {}); setProsumStep(1); setDossierPage("all"); load();
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
      await api.put(`/data/prosumator/${editId}`, { ...form, checklist: checks });
      toast.success(`${label}: salvat`);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || `Nu am putut salva secțiunea „${label}”`);
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
      <PageHeader eyebrow={cfg.eyebrow} title={cfg.title} sub={cfg.sub}
        action={<div className="flex gap-2 flex-wrap">
          {key === "prosumator" && <AiImportButton onExtracted={(d) => { setForm(d); setEditId(null); setChecks({}); }} />}
          <Btn data-testid="add-btn" onClick={form ? () => setForm(null) : openNew}>{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> {cfg.addLabel}</>}</Btn>
        </div>} />

      {form && (
        <div className="den-panel mb-6 scroll-mt-20" id={key === "prosumator" && editId ? "dossier-top" : undefined} data-testid="module-form">
          {key === "prosumator" && !editId ? <>
            <div className="flex items-start justify-between gap-4 mb-5">
              <div className="mb-4"><h2 className="text-lg font-bold">Dosar nou</h2><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>3 pași scurți — restul datelor se completează apoi în dosar.</p></div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-5" aria-label={`Pasul ${prosumStep} din 3`}>
              {["Client", "Loc de consum", "Tip cerere"].map((step, idx) => <div key={step} className={`rounded-lg border px-2 py-2 text-center text-[10px] sm:text-[11px] font-semibold ${prosumStep === idx + 1 ? "den-wizard-active" : ""}`} style={{ borderColor: prosumStep === idx + 1 ? "var(--green)" : "var(--line)", color: prosumStep === idx + 1 ? "var(--green)" : "var(--muted)", background: prosumStep === idx + 1 ? "#edf7f0" : "transparent" }}><span className="mr-1 inline-grid h-4 w-4 place-items-center rounded-full" style={{ background: prosumStep > idx + 1 ? "var(--green)" : "#eeeae1", color: prosumStep > idx + 1 ? "white" : "var(--muted)" }}>{prosumStep > idx + 1 ? "✓" : idx + 1}</span>{step}</div>)}
            </div>
          </> : editId && key === "prosumator" ? <div className="mb-4" data-testid="dossier-detail-heading">
            <button type="button" onClick={() => { setForm(null); setEditId(null); }} className="mb-3 text-xs font-medium" style={{ color: "var(--muted)" }}>← Dosare</button>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0"><div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h2 className="text-xl font-extrabold" style={{ color: "var(--green)" }}>Dosar {form.number || `#${editId}`}</h2><span className="text-lg font-bold">{form.client_name || "Beneficiar neprecizat"}</span></div>
                <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{[form.locality, form.county].filter(Boolean).join(", ")}{form.operator ? ` · ${form.operator}` : ""}</p>
                <div className="mt-2 flex flex-wrap gap-2"><span className="rounded-full px-3 py-1 text-[11px] font-bold" style={{ background: "#edf7f0", color: "var(--green)" }}>{displayStatus(form)}</span>{form.request_type && <span className="rounded-full px-3 py-1 text-[11px] font-bold" style={{ background: "#fff5e8", color: "#9a5c12" }}>{form.request_type}</span>}</div>
              </div>
              <Btn variant="secondary" onClick={() => remove(editId)}><Trash2 size={14} /> Șterge dosarul</Btn>
            </div>
          </div> : <h2 className="text-lg font-bold mb-5">{editId ? "Editează înregistrarea" : cfg.addLabel}</h2>}
          {key === "prosumator" && editId && <nav className="sticky top-[54px] z-20 mb-5 flex gap-2 overflow-x-auto border-b bg-white/95 pb-2 pt-1 backdrop-blur md:top-0" aria-label="Navigare în dosar">
            {[ ["all", "Dosar complet", "dossier-top"], ["client", "Client", "dossier-section-client"], ["location", "Loc de consum", "dossier-section-location"], ["request", "Cererea", "dossier-section-request"], ["installation", "Instalație", "dossier-section-installation"], ["documents", "Acte & semnare", "dossier-section-documents"], ["equipment", "Echipamente", "dossier-section-equipment"], ["team", "Echipă", "dossier-section-team"], ["pif", "Teste și PIF", "dossier-section-pif"], ["other", "Mesaje", "dossier-section-messages"], ["timeline", "Jurnal", "dossier-section-timeline"] ].map(([id, label, target]) => <button key={id} type="button" aria-current={dossierPage === id ? "location" : undefined} onClick={() => { setDossierPage(id); document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" }); }} className="shrink-0 rounded-lg px-3 py-2 text-xs font-bold" style={dossierPage === id ? { background: "var(--navy)", color: "white" } : { background: "var(--bg)", color: "var(--muted)" }} data-testid={`dossier-page-${id}`}>{label}</button>)}
          </nav>}
          {key === "prosumator" && editId && <SummaryStrip form={form} />}
          {key === "prosumator" && editId && <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="dossier-quick-actions">
            {[
              ["schema", "Schema monofilară (PDF)", `/sld/${editId}/pdf?auth=${localStorage.getItem("den_token")}`],
              ["dossier", "Dosar prosumator (PDF)", `/docs/all/${editId}?auth=${localStorage.getItem("den_token")}`],
              ["pram", "Buletin PRAM", `/docs/buletin_priza/${editId}?auth=${localStorage.getItem("den_token")}`],
              ["pv", "PV probe", `/docs/pv_teste/${editId}?auth=${localStorage.getItem("den_token")}`],
            ].map(([id, label, path]) => <a key={id} href={`${API}${path}`} target="_blank" rel="noopener noreferrer" className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid={`dossier-quick-${id}`}>{label}</a>)}
            <button type="button" onClick={() => document.getElementById("dossier-section-equipment")?.scrollIntoView({ behavior: "smooth", block: "start" })} className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="dossier-quick-equipment">Echipamente</button>
            <button type="button" onClick={() => document.getElementById("dossier-section-documents")?.scrollIntoView({ behavior: "smooth", block: "start" })} className="rounded-lg border bg-white px-3 py-3 text-left text-xs font-bold" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="dossier-quick-documents">Acte & semnare</button>
          </div>}
          {key === "prosumator" && editId ? <DossierFieldSections fields={cfg.fields} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} onSaveSection={saveDossierSection} /> : key === "prosumator" && !editId ? <div className="grid sm:grid-cols-2 gap-4" data-testid="new-dossier-simple-step">
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

          {key === "prosumator" && editId && <div id="dossier-section-documents" className="scroll-mt-24"><DossierOpis id={editId} /><GeneratedDocs id={editId} files={form.files} /><SignRequests dossierId={editId} /></div>}
          {key === "prosumator" && editId && <div id="dossier-section-equipment" className="mt-6 scroll-mt-24"><div className="flex items-center justify-between gap-3"><h3 className="font-bold text-base">Echipamente și parametri instalației</h3><button type="button" onClick={() => saveDossierSection("Echipamente")} className="rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button></div><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Alege modelul și puterea din catalog. Stringurile, bateriile, totalurile și dimensionarea se actualizează pe baza selecției; verifică datele înainte de generarea documentelor.</p><QuickEquipment form={form} catalog={equipmentCatalog} onChange={(patch) => setForm((current) => ({ ...current, ...patch }))} /><details className="mt-4 rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-sm font-bold">Configurator tehnic avansat</summary><div className="mt-4"><CefEditor value={form.cef} onChange={(v) => setVal("cef", v)} /></div></details><SldPanel id={editId} form={form} setVal={setVal} /></div>}
          {key === "prosumator" && editId && <div id="dossier-section-team" className="mt-6 scroll-mt-24"><div className="flex items-center justify-between gap-3"><h3 className="font-bold text-base">Echipă & semnături</h3><button type="button" onClick={() => saveDossierSection("Echipă & semnături")} className="rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button></div><DossierExtras form={form} setVal={setVal} view="team" /></div>}
          {key === "prosumator" && editId && <div id="dossier-section-pif-tools" className="mt-6 scroll-mt-24"><div className="mb-3 flex items-center justify-between gap-3"><h3 className="font-bold text-base">Reglaje și punere în funcțiune</h3><button type="button" onClick={() => saveDossierSection("Teste și PIF")} className="rounded-lg border px-3 py-1.5 text-[11px] font-bold" style={{ borderColor: "var(--line)", color: "var(--green)" }}>Salvează</button></div><DossierExtras form={form} setVal={setVal} view="pif" /><PifPanel id={editId} /></div>}
          {key === "prosumator" && editId && <div id="dossier-section-messages" className="mt-6 space-y-4 scroll-mt-24"><AssignBox value={form.assigned_to} onChange={(v) => setVal("assigned_to", v)} /><DossierMessages id={editId} /><SimpleDossierBtn id={editId} /><AiDossierCheck id={editId} /></div>}
          {key === "prosumator" && editId && <div id="dossier-section-timeline" className="mt-6 scroll-mt-24"><DossierTimeline id={editId} /></div>}
          {key === "power" && <PowerDossier id={editId} form={form} setVal={setVal} />}
          {key === "atr" && <AtrDossier id={editId} form={form} setVal={setVal} />}
          {key === "diu" && editId && <DiuDossier id={editId} form={form} setVal={setVal} setForm={setForm} savedAt={savedAt} />}
          {key === "diu" && editId && <SignRequests dossierId={editId} module="diu" />}
          {key === "diu" && editId && <AiPrecheck id={editId} base="diu" open={diuPre} onClose={() => setDiuPre(false)} onFinalize={doSave} form={form}
            title="Verificare AI înainte de predarea către beneficiar" action="Salvează ca „Predat beneficiarului”" />}
          {key === "clients" && editId && <ClientDocs client={form} onChange={(docs) => setVal("docs", docs)} />}
          {key === "clients" && editId && <SignRequests clientName={form.name} />}

          {!(key === "prosumator" && !editId) && <div className={`flex gap-2 mt-6 den-noprint ${key === "prosumator" && editId ? "sticky bottom-2 z-20 rounded-xl border bg-white/95 p-3 shadow-lg backdrop-blur" : ""}`} style={key === "prosumator" && editId ? { borderColor: "var(--line)" } : undefined}>
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
            <button onClick={() => setDossierView("kanban")} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${dossierView === "kanban" ? "text-white" : ""}`} style={dossierView === "kanban" ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-kanban"><LayoutGrid size={14} /> Kanban</button>
            <button onClick={() => setDossierView("list")} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${dossierView === "list" ? "text-white" : ""}`} style={dossierView === "list" ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-list"><List size={14} /> Listă</button>
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
        ) : key === "prosumator" && dossierView === "kanban" ? (
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


