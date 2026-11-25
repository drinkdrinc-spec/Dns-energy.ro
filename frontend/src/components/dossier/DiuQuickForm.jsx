import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { hasConfiguredStorage } from "@/lib/cefStorage";

const CORE = new Set(["client_name", "type", "power", "address", "operator", "atr", "status"]);
const norm = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
const isBlank = (value) => value == null || value === "" || (Array.isArray(value) && value.length === 0)
  || (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0);

const SITE_FIELDS = ["address", "county", "locality", "pod", "operator", "supplier", "cf_nr", "cadastral_nr", "nlc"];
const SOURCE_FIELDS = ["power", "atr", "type", "supply", "earthing", "bmp_a", "tg_breaker_a", "meter_enabled", "meter",
  "meter_serial", "meter_specs", "column_cable", "memoriu_desc", "relay", "breaker", "mono_ref", "pram_ref", "grounding_limit"];
function clientSites(client) {
  const saved = Array.isArray(client?.consumption_sites)
    ? client.consumption_sites.filter((site) => site && typeof site === "object").map((site, index) => ({ ...site, id: String(site.id || ("saved-" + index)) }))
    : [];
  if (saved.length) return saved;
  if (["address", "pod", "locality", "county"].some((key) => String(client?.[key] || "").trim())) {
    return [{ id: "legacy", ...Object.fromEntries(SITE_FIELDS.map((key) => [key, client?.[key] || ""])) }];
  }
  return [];
}
function siteFor(client, preferredPod) {
  const sites = clientSites(client);
  const pod = String(preferredPod || "").replace(/\s+/g, "").toUpperCase();
  return (pod && sites.find((site) => String(site.pod || "").replace(/\s+/g, "").toUpperCase() === pod)) || sites[0] || null;
}
const siteLabel = (site, index) => [site.address, site.locality, site.county, site.pod && ("POD " + site.pod)].filter(Boolean).join(" · ") || ("Loc de consum " + (index + 1));

function prosumerRecords(client, records) {
  return records.filter((item) => item.client_id
    ? item.client_id === client?.id
    : norm(item.client_name) === norm(client?.name || client?.label));
}
function prosumerForSite(site, records) {
  if (!site) return records.length === 1 ? records[0] : null;
  const pod = String(site.pod || "").replace(/\s+/g, "").toUpperCase();
  if (pod) {
    const exact = records.filter((item) => String(item.pod || "").replace(/\s+/g, "").toUpperCase() === pod);
    if (exact.length === 1) return exact[0];
    if (records.some((item) => item.pod)) return null;
  }
  const address = norm(site.address).replace(/[^a-z0-9]/g, "");
  if (address) {
    const exact = records.filter((item) => norm(item.address).replace(/[^a-z0-9]/g, "") === address);
    if (exact.length === 1) return exact[0];
    if (records.some((item) => item.address)) return null;
  }
  return records.length === 1 ? records[0] : null;
}
function prosumerDefaults(pros, client, site, status) {
  if (!pros) return {};
  const grid = pros.cef?.grid || {};
  const inverters = pros.cef?.inverters || [];
  const circuits = inverters.map((inverter, index) => {
    const ac = inverter.ac || {};
    const count = Math.max(1, Number(inverter.count) || 1);
    return {
      name: `INV${index + 1} — ${inverter.brand_model || "invertor"}${count > 1 ? ` × ${count} buc.` : ""}`,
      breaker_a: ac.breaker_a || "", curve: ac.curve || "C", section: ac.section || "",
      cable: ac.cable_type || "", length: ac.length_m || "", rcd_ma: inverter.rcd_ma || "",
      rcd_type: String(inverter.rcd_type || "").replace(/Tip/i, "").trim(),
    };
  });
  const address = pros.address || site?.address || client?.address || "";
  const panelKwp = Number(pros.cef?.total_kw || pros.panel_kw || pros.pv_kw || 0);
  const inverterNames = inverters.map((item) => item.brand_model).filter(Boolean);
  const batteryNames = [
    ...(pros.cef?.shared_batteries || []).map((item) => item.brand_model || item.model),
    ...inverters.map((item) => item.battery?.model).filter(Boolean),
  ].filter(Boolean);
  const description = [
    "Instalație fotovoltaică",
    panelKwp ? `${panelKwp} kWp panouri` : "",
    inverterNames.length ? `invertor(e): ${[...new Set(inverterNames)].join(", ")}` : "",
    batteryNames.length ? `stocare: ${[...new Set(batteryNames)].join(", ")}` : "",
    grid.backup_mode && grid.backup_mode !== "—" ? `regim backup: ${grid.backup_mode}` : "",
    grid.anti_required ? "protecție antiinsularizare cerută conform datelor instalației" : "",
  ].filter(Boolean).join("; ");
  const columnCable = grid.column_cable || grid.main_column_cable || grid.main_column_cable_proposal || "";
  const relay = grid.anti_relay || grid.relay || "";
  const breaker = grid.anti_breaker || grid.teg_main_protection || grid.tg_breaker || "";
  return {
    client_name: client?.label || client?.name || pros.client_name || "",
    client_id: client?.id || pros.client_id || "",
    client_site_id: site?.id || "",
    address, operator: pros.operator || site?.operator || client?.operator || "",
    pod: pros.pod || site?.pod || client?.pod || "",
    county: site?.county || client?.county || "", locality: site?.locality || client?.locality || "",
    supplier: site?.supplier || client?.supplier || "", cf_nr: site?.cf_nr || client?.cf_nr || "",
    cadastral_nr: site?.cadastral_nr || client?.cadastral_nr || "", nlc: site?.nlc || client?.nlc || "",
    power: pros.inverter_kw || pros.power || pros.cef?.total_kw || "", atr: pros.atr || "",
    type: hasConfiguredStorage(pros) ? "Sistem fotovoltaic hibrid" : "Sistem fotovoltaic on-grid",
    supply: pros.supply || grid.supply || "", earthing: grid.earthing || "",
    bmp_a: grid.bmp_a || "", tg_breaker_a: grid.tg_breaker_a || "",
    meter_enabled: grid.meter_enabled ?? grid.meter ?? "", meter: grid.meter || "",
    meter_serial: grid.meter_serial || "", meter_specs: grid.meter_specs || "",
    column_cable: columnCable,
    memoriu_desc: description,
    relay,
    breaker,
    ...(pros.mono_ref ? { mono_ref: pros.mono_ref } : {}),
    ...(pros.pram_ref ? { pram_ref: pros.pram_ref } : {}),
    ...(grid.grounding_limit || pros.grounding_limit ? { grounding_limit: grid.grounding_limit || pros.grounding_limit } : {}),
    circuits, status: status || "În lucru",
    ...(pros.receptie_date ? { receptie_date: pros.receptie_date } : {}),
    ...(pros.pif_date ? { pif_date: pros.pif_date } : {}),
    ...(pros.grounding_ohm || grid.grounding_ohm ? { pram_m: { earth_ohm: grid.grounding_ohm || pros.grounding_ohm } } : {}),
  };
}


function Field({ f, form, setVal, refOptions }) {
  if (f.type === "section") return <h4 className="sm:col-span-2 mt-3 border-t pt-3 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h4>;
  const value = form[f.name] ?? "";
  const common = { className: "den-input", value, onChange: (e) => setVal(f.name, e.target.value), "data-testid": `field-${f.name}` };
  return <label className={`den-field ${f.full ? "sm:col-span-2" : ""}`} key={f.name}><span>{f.label}</span>
    {f.type === "textarea" ? <textarea {...common} rows={3} />
      : f.type === "select" ? <select {...common}><option value="">Alege...</option>
        {value && !(f.options || []).includes(value) && <option value={value}>{value} · de confirmat</option>}
        {(f.options || []).map((option) => <option key={option} value={option}>{option}</option>)}</select>
        : f.type === "ref" ? <select {...common}><option value="">Alege...</option>{(refOptions[f.ref] || []).map((option) => <option key={option.id} value={option.label}>{option.label}</option>)}</select>
          : <input {...common} type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"} step={f.type === "number" ? "any" : undefined} />}
  </label>;
}

export function DiuQuickForm({ cfg, form, setVal, refOptions }) {
  const [pros, setPros] = useState([]);
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, []);
  const showTests = new URLSearchParams(window.location.search).get("showTests") === "1";
  const clients = (refOptions.clients || []).filter((c) => showTests || !/\bTEST\b/i.test(String(c.label || "")));
  const selectedClient = clients.find((c) => c.id === form.client_id) || clients.find((c) => c.label === form.client_name);
  const linked = (selectedClient ? prosumerRecords(selectedClient, pros) : [])
    .filter((p) => showTests || !/\bTEST\b/i.test([p.number, p.client_name].filter(Boolean).join(" ")));
  const chosenPros = linked.find((p) => p.id === form.pros_id) || null;
  useEffect(() => {
    if (!selectedClient) return;
    const currentSite = clientSites(selectedClient).find((item) => String(item.id) === String(form.client_site_id))
      || siteFor(selectedClient);
    const p = (form.pros_id && linked.find((item) => item.id === form.pros_id)) || prosumerForSite(currentSite, linked);
    if (!p) return;
    if (!form.pros_id) setVal("pros_id", p.id);
    for (const [key, value] of Object.entries(prosumerDefaults(p, selectedClient, currentSite, form.status))) {
      if (isBlank(form[key]) && value !== "" && value !== undefined) setVal(key, value);
    }
  }, [selectedClient?.id, linked.length, form.pros_id, form.client_site_id]);
  useEffect(() => {
    const operator = chosenPros?.operator || selectedClient?.operator || "";
    if (operator && !form.operator) setVal("operator", operator);
  }, [chosenPros?.id, selectedClient?.id, form.operator]);
  const choosePros = (id) => {
    setVal("pros_id", id);
    const p = linked.find((item) => item.id === id);
    if (!p) return;
    for (const key of SOURCE_FIELDS) setVal(key, "");
    setVal("circuits", []);
    setVal("pram_m", {});
    const site = siteFor(selectedClient, p.pod);
    const values = prosumerDefaults(p, selectedClient, site, form.status);
    Object.entries(values).forEach(([key, value]) => { if (value !== "" && value !== undefined) setVal(key, value); });
  };
  const chooseClient = (label) => {
    const client = clients.find((c) => c.label === label);
    const site = siteFor(client);
    setVal("client_name", label);
    setVal("client_id", client?.id || "");
    setVal("client_site_id", site?.id || "");
    setVal("pros_id", "");
    for (const key of SOURCE_FIELDS) setVal(key, "");
    setVal("circuits", []);
    setVal("pram_m", {});
    for (const field of SITE_FIELDS) setVal(field, site?.[field] || client?.[field] || "");
    setVal("address", site?.address || client?.address || "");
    setVal("operator", site?.operator || client?.operator || "");
    setVal("status", form.status || "În lucru");
    const matches = client ? prosumerRecords(client, pros) : [];
    const p = prosumerForSite(site, matches);
    if (p) {
      setVal("pros_id", p.id);
      Object.entries(prosumerDefaults(p, client, site, form.status)).forEach(([key, value]) => {
        if (value !== "" && value !== undefined) setVal(key, value);
      });
    }
  };
  const fieldByName = (name) => (cfg.fields || []).find((f) => f.name === name);
  const extras = (cfg.fields || []).filter((f) => f.type === "section" || !CORE.has(f.name));

  return <div id="diu-client-racordare" className="space-y-4" data-testid="diu-quick-form">
    <section className="rounded-2xl border p-4 sm:p-5" style={{ borderColor: "var(--line)", background: "linear-gradient(135deg, #f2f7ff 0%, #fff 76%)" }}>
      <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>Predare lucrare · DI-U</p>
      <h3 className="mt-1 text-lg font-bold">Pornește din client și instalație</h3>
      <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>Selectează clientul. Dacă are dosar de prosumator asociat, datele cunoscute se completează automat.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="den-field sm:col-span-2"><span>Beneficiar / client *</span><select className="den-input" value={selectedClient?.label || ""} onChange={(e) => chooseClient(e.target.value)} data-testid="diu-client-select">
          <option value="">Selectează clientul...</option>{clients.map((c) => <option key={c.id} value={c.label}>{c.label}</option>)}
        </select></label>
        {selectedClient && clientSites(selectedClient).length > 0 && <label className="den-field sm:col-span-2" data-testid="diu-consumption-site-selector"><span>Loc de consum al clientului</span>
          <select className="den-input" value={form.client_site_id || siteFor(selectedClient, chosenPros?.pod)?.id || ""} onChange={(event) => {
            const site = clientSites(selectedClient).find((item) => String(item.id) === String(event.target.value));
            if (!site) return;
            for (const key of SOURCE_FIELDS) setVal(key, "");
            setVal("circuits", []);
            setVal("pram_m", {});
            setVal("client_site_id", site.id);
            for (const field of SITE_FIELDS) setVal(field, site[field] || "");
            const matchingPros = prosumerForSite(site, linked);
            setVal("pros_id", matchingPros?.id || "");
            if (matchingPros) Object.entries(prosumerDefaults(matchingPros, selectedClient, site, form.status))
              .forEach(([key, value]) => { if (value !== "" && value !== undefined) setVal(key, value); });
          }} data-testid="diu-consumption-site-select">
            {clientSites(selectedClient).map((site, index) => <option key={site.id} value={site.id}>{siteLabel(site, index)}</option>)}
          </select>
        </label>}
        {selectedClient && linked.length > 1 && <label className="den-field sm:col-span-2"><span>Dosar prosumator asociat</span><select className="den-input" value={form.pros_id || ""} onChange={(e) => choosePros(e.target.value)} data-testid="diu-pros-select">
          <option value="">Selectează locul de consum...</option>{linked.map((p) => <option key={p.id} value={p.id}>{p.number || "Dosar"} · POD {p.pod || "—"} · {p.address || p.client_name}</option>)}
        </select></label>}
        {!selectedClient && <p className="sm:col-span-2 text-xs" style={{ color: "var(--muted)" }}>Alege întâi clientul pentru a vedea dosarele de prosumator asociate.</p>}
        {(["type", "power", "address", "operator", "atr", "status"].map((name) => {
          const f = fieldByName(name); return f && <Field key={name} f={f} form={form} setVal={setVal} refOptions={refOptions} />;
        }))}
        {chosenPros && <div className="sm:col-span-2 rounded-lg border bg-white px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid="diu-linked-summary">
          <b>Date preluate din dosarul prosumator:</b> POD {chosenPros.pod || "—"} · {chosenPros.operator || "operator necompletat"} · invertor {chosenPros.inverter_kw || chosenPros.power || "—"} kW
          {hasConfiguredStorage(chosenPros) && " · baterie inclusă"}
        </div>}
      </div>
    </section>
    <details className="rounded-xl border px-4" style={{ borderColor: "var(--line)" }} data-testid="diu-advanced-fields">
      <summary className="cursor-pointer py-3 text-sm font-semibold">Date tehnice și de recepție suplimentare</summary>
      <div className="grid gap-3 pb-4 sm:grid-cols-2">{extras.map((f, i) => f.type === "section"
        ? <Field key={`section-${i}`} f={f} form={form} setVal={setVal} refOptions={refOptions} />
        : <Field key={f.name} f={f} form={form} setVal={setVal} refOptions={refOptions} />)}</div>
    </details>
  </div>;
}


