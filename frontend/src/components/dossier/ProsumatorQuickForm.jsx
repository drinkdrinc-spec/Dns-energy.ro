import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { hasConfiguredStorage } from "@/lib/cefStorage";

const field = (cfg, name) => (cfg.fields || []).find((f) => f.name === name);
const title = (f, fallback) => f?.label?.replace(/\s*\*$/, "") || fallback;
const selectStyle = { borderColor: "var(--line)" };

function supplierCatalogBlockReason(item) {
  if (item?.category !== "Invertor" || !item?.supplier) return "";
  const model = String(item.brand_model || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (/\b(?:kit|bundle|pachet)\b|\bcu\s+(?:baterie|acumulator)\b|\bwith\s+(?:battery|accumulator)\b|\b(?:baterie|acumulator)\s+inclus/.test(model)
      || /\b(?:invertor|inverter)\b.*(?:\+|&|\band\b).*\b(?:baterie|acumulator|battery)\b/.test(model)) {
    return "Pachet cu baterie — nu este un model individual de invertor";
  }
  const titlePower = model.match(/\b(\d+(?:[.,]\d+)?)\s*kw\b/);
  const catalogPower = Number(item.p_nom_kw);
  if (titlePower && Number.isFinite(catalogPower) && catalogPower > 0) {
    const namedPower = Number(titlePower[1].replace(",", "."));
    if (Math.abs(namedPower - catalogPower) > Math.max(0.1, namedPower * 0.03)) {
      return `Puterea din denumire (${namedPower} kW) diferă de catalog (${catalogPower} kW)`;
    }
  }
  return "";
}

// Propose strings only when both catalog datasheets provide the limits needed to check them.
function panelCountForPower(powerKw, panelW) {
  const kw = Number(powerKw), watts = Number(panelW);
  return kw > 0 && watts > 0 ? Math.ceil((kw * 1000) / watts) : "";
}

function datasheetNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const parsed = Number(String(value).trim().replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}
const hasStoredCatalogDocument = (item, kind) => Boolean(item?.[kind]?.storage_path);
function batteryCatalogData(item, phases) {
  const breakerCurrent = item.breaker_a ?? item.dc_switch_current_a;
  const breakerVoltage = item.breaker_voltage_dc ?? item.dc_switch_voltage_v;
  const threePhase = String(phases || "").toLowerCase().includes("tri");
  return {
    catalog_id: item.id,
    model: item.brand_model,
    kwh: item.kwh,
    ah: item.ah,
    voltage: threePhase ? (item.voltage_3ph ?? item.voltage) : (item.voltage_1ph ?? item.voltage),
    voltage_1ph: item.voltage_1ph,
    voltage_3ph: item.voltage_3ph,
    i_max: item.i_max,
    i_max_source_url: item.i_max_source_url,
    max_fuse_a: item.max_fuse_a,
    coupling: item.coupling || "",
    breaker_a: breakerCurrent,
    breaker_voltage_dc: breakerVoltage,
    breaker_integrated: item.breaker_integrated,
    breaker_poles: item.breaker_poles,
    breaker_icu_ka: item.breaker_icu_ka,
    dc_switch_voltage_v: item.dc_switch_voltage_v ?? breakerVoltage,
    dc_switch_current_a: item.dc_switch_current_a ?? breakerCurrent,
    breaker_source_url: item.breaker_source_url,
    datasheet_url: item.datasheet_url,
    conformity_url: item.conformity_url,
  };
}


function proposeStrings(inv, totalPanels) {
  const count = Math.floor(datasheetNumber(totalPanels) || 0);
  const mppts = Math.floor(datasheetNumber(inv.mppt_count) || 0);
  const voc = datasheetNumber(inv.panel_voc), vmp = datasheetNumber(inv.panel_vmp), isc = datasheetNumber(inv.panel_isc);
  const vocCoef = datasheetNumber(inv.panel_coef_voc), vmpCoef = datasheetNumber(inv.panel_coef_vmp);
  const maxDc = datasheetNumber(inv.vdc_max), mpptMin = datasheetNumber(inv.mppt_min), mpptMax = datasheetNumber(inv.mppt_max);
  const maxCurrent = datasheetNumber(inv.imax_mppt);
  const required = [voc, vmp, isc, vocCoef, vmpCoef, maxDc, mpptMin, mpptMax, maxCurrent];
  if (!count || !mppts || required.some((value) => value === null)
      || [voc, vmp, isc, maxDc, mpptMin, mpptMax, maxCurrent].some((value) => value <= 0)
      || mpptMin > mpptMax || isc > maxCurrent) return null;
  const stringCount = Math.min(count, mppts);
  const base = Math.floor(count / stringCount), remainder = count % stringCount;
  const panelCounts = Array.from({ length: stringCount }, (_, i) => base + (i < remainder ? 1 : 0));
  const valid = panelCounts.every((n) => {
    const vocCold = n * voc * (1 + (vocCoef / 100) * (-10 - 25));
    const vmpHot = n * vmp * (1 + (vmpCoef / 100) * (70 - 25));
    const vmpStc = n * vmp;
    return vocCold > 0 && vocCold <= maxDc && vmpHot >= mpptMin && vmpStc <= mpptMax;
  });
  if (!valid) return null;
  return panelCounts.map((panels, i) => ({ panels, mppt: i + 1, auto_generated: true }));
}

export function ProsumatorQuickForm({ cfg, form, setVal, refOptions, onImportsBusyChange }) {
  const [catalog, setCatalog] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [problem, setProblem] = useState("");
  const [catalogSearch, setCatalogSearch] = useState({});
  const [addingModel, setAddingModel] = useState({});
  const [catalogDocStatus, setCatalogDocStatus] = useState("");
  const pendingDocImports = useRef(0);
  const formRef = useRef(form);
  formRef.current = form;
  useEffect(() => {
    api.get("/data/catalog").then((r) => setCatalog(Array.isArray(r.data) ? r.data : [])).catch(() => setProblem("Catalogul nu s-a putut încărca. Poți salva datele de bază și selecta echipamentele ulterior.")).finally(() => setCatalogLoading(false));
  }, []);
  const clients = (refOptions.clients || []).filter((client) => !/\bTEST\b/i.test(String(client.label || client.name || "")));
  const selectedClientMatches = clients.filter((client) => client.label === form.client_name);
  const selectedClient = clients.find((client) => client.id === form.client_id)
    || (selectedClientMatches.length === 1 ? selectedClientMatches[0] : null);
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
        if (supplierCatalogBlockReason(item)) return false;
        // Keep legacy seed rows with electrical values contradicted by the attached manufacturer sheet out of new designs.
        if (item.category === "Panou" && item.brand_model === "Aiko Neostar 475 W"
          && Number(item.voc) === 40.2 && Number(item.vmp) === 33.6 && Number(item.isc) === 14.9 && Number(item.imp) === 14.15) return false;
        if (item.category === "Panou" && item.brand_model === "LONGi Hi-MO 6 LR5-54HTH-440M"
          && Number(item.voc) === 39.9 && Number(item.vmp) === 33.3 && Number(item.isc) === 14.04 && Number(item.imp) === 13.22) return false;
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
  const blockedSupplierModels = useMemo(() => catalog
    .filter((item) => Boolean(supplierCatalogBlockReason(item))), [catalog]);
  const blockedSelectedModels = blockedSupplierModels.filter((item) => Object.values(selected).includes(item.id));

  const cefUpdate = (kind, item, id, panelCountOverride) => {
    const currentForm = formRef.current;
    const cef = currentForm.cef || { grid: {}, inverters: [], shared_batteries: [] };
    const old = cef.inverters?.[0] || { id: "main", strings: [], ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "H1Z2Z2-K" }, battery_mode: "none" };
    const inv = { ...old };
    const existingStrings = inv.strings || [];
    const canReplaceStrings = existingStrings.length === 0 || existingStrings.every((x) => x.auto_generated);
    if (kind === "inverter") Object.assign(inv, item ? {
      catalog_id: item.id, brand_model: item.brand_model, type: item.type, phases: item.phases, p_nom_kw: item.p_nom_kw, p_max_kw: item.p_max_kw,
      vdc_max: item.vdc_max, mppt_min: item.mppt_min, mppt_max: item.mppt_max, mppt_count: item.mppt_count, imax_mppt: item.imax_mppt, bat_i_max: item.bat_i_max,
      red_limit_mode: item.red_limit_mode || "Nu este declarată", count: Math.max(1, Number(currentForm.inverter_count) || 1),
    } : { catalog_id: "", brand_model: "", p_nom_kw: "", p_max_kw: "", type: "", phases: "", count: 1 });
    if (kind === "panel") Object.assign(inv, item ? {
      panel_catalog_id: item.id, panel_model: item.brand_model, panel_w: item.w, panel_voc: item.voc, panel_vmp: item.vmp,
      panel_isc: item.isc, panel_coef_voc: item.coef_voc, panel_coef_vmp: item.coef_vmp,
    } : { panel_catalog_id: "", panel_model: "", panel_w: "", panel_voc: "", panel_vmp: "", panel_isc: "", panel_coef_voc: "", panel_coef_vmp: "" });
    if (kind === "battery") Object.assign(inv, item ? {
      battery_mode: "own", battery: { ...(inv.battery || {}), ...batteryCatalogData(item, inv.phases), modules: Number(currentForm.battery_count || 1) },
    } : { battery_mode: "none", battery: {} });
    if (kind === "meter") setVal("cef", { ...cef, grid: { ...(cef.grid || {}), meter: item?.brand_model || "", meter_catalog_id: item?.id || "" } });
    else {
      if (canReplaceStrings) {
        const proposal = proposeStrings(inv, panelCountOverride ?? currentForm.panel_count);
        if (proposal) inv.strings = proposal;
        else if (existingStrings.every((x) => x.auto_generated)) inv.strings = [];
      }
      const nextCef = { ...cef, grid: { ...(cef.grid || {}), ...(currentForm.supply ? { supply: currentForm.supply } : {}), ...(currentForm.bransament_kw ? { bransament_kw: Number(currentForm.bransament_kw) } : {}) }, inverters: [inv, ...(cef.inverters || []).slice(1)] };
      setVal("cef", nextCef);
      if (kind === "inverter" || kind === "battery") {
        const hasBattery = hasConfiguredStorage({ cef: nextCef });
        const hasHybridInverter = (nextCef.inverters || []).some((row) => row.type === "Hibrid");
        setVal("system_type", hasBattery ? "Hibrid cu baterie" : hasHybridInverter ? "Hibrid" : "On-grid");
      }
    }
    if (id === "") setVal("catalog_selection", { ...selected, [kind]: "" });
  };

  const choose = (kind, id, providedItem = null) => {
    const currentForm = formRef.current;
    const item = providedItem || options[kind].find((x) => x.id === id);
    let panelCountOverride;
    setVal("catalog_selection", { ...selected, [kind]: id || "" });
    if (kind === "inverter") {
      setVal("inverter", item?.brand_model || ""); setVal("inverter_kw", item?.p_nom_kw || "");
      setVal("inverter_count", item ? (currentForm.inverter_count || 1) : "");

    } else if (kind === "panel") {
      setVal("panels", item?.brand_model || ""); setVal("panel_w", item?.w || "");
      const suggestedCount = item ? panelCountForPower(currentForm.power, item.w) : "";
      const hasSavedCount = currentForm.panel_count !== undefined && currentForm.panel_count !== null && String(currentForm.panel_count).trim() !== "";
      const autoMode = Boolean(item) && (currentForm.panel_count_auto === true || (!hasSavedCount && currentForm.panel_count_auto !== false));
      const useSuggestion = Boolean(suggestedCount) && autoMode;
      panelCountOverride = useSuggestion ? suggestedCount : undefined;
      setVal("panel_count", useSuggestion ? suggestedCount : (item ? (currentForm.panel_count || "") : ""));
      setVal("panel_count_auto", autoMode);
    } else if (kind === "battery") {
      setVal("battery", item?.brand_model || ""); setVal("battery_kwh", item?.kwh || "");
      setVal("battery_v", item?.voltage || ""); setVal("battery_ah", item?.ah || "");
      setVal("battery_coupling", item?.coupling || ""); setVal("battery_count", item ? (currentForm.battery_count || 1) : "");

    } else setVal("smart_meter_type", item?.brand_model || "");
    cefUpdate(kind, item, id, panelCountOverride);
    if (item && kind !== "meter") {
      const documents = ["datasheet", "conformity"].filter((documentKind) =>
        item[documentKind + "_url"] && !item[documentKind]?.storage_path
      );
      if (documents.length) {
        pendingDocImports.current += 1;
        onImportsBusyChange?.(true);
        const docLabels = { datasheet: "fișa tehnică", conformity: "declarația de conformitate" };
        setCatalogDocStatus("Se preiau automat " + documents.map((key) => docLabels[key]).join(" și ") + " pentru " + item.brand_model + "…");
        Promise.all(documents.map(async (documentKind) => {
          try {
            await api.post("/catalog/" + encodeURIComponent(item.id) + "/import-document", { kind: documentKind, url: item[documentKind + "_url"] }, { timeout: 45000 });
            return { kind: documentKind, ok: true };
          } catch (error) {
            return { kind: documentKind, ok: false, reason: error.response?.data?.detail || "sursa oficială nu a putut fi preluată" };
          }
        })).then(async (results) => {
          const failures = results.filter((result) => !result.ok);
          if (results.some((result) => result.ok)) {
            const refreshed = await api.get("/data/catalog").catch(() => null);
            if (Array.isArray(refreshed?.data)) setCatalog(refreshed.data);
          }
          setCatalogDocStatus(failures.length
            ? "Modelul a fost ales, dar unele documente nu s-au preluat: " + failures.map((failure) => docLabels[failure.kind] + " — " + failure.reason).join("; ") + "."
            : "Documentele oficiale pentru " + item.brand_model + " au fost importate și se atașează la salvarea dosarului.");
        }).finally(() => {
          pendingDocImports.current = Math.max(0, pendingDocImports.current - 1);
          if (pendingDocImports.current === 0) onImportsBusyChange?.(false);
        });
      } else if (item.datasheet?.storage_path || item.conformity?.storage_path) {
        setCatalogDocStatus("Documentele deja încărcate pentru " + item.brand_model + " se vor atașa la salvarea dosarului.");
      } else {
        setCatalogDocStatus("Nu există link oficial pentru documentele " + item.brand_model + ". Modelul rămâne selectat; adaugă sursele în Catalog echipamente.");
      }
    }
  };

  const [supplierSearch, setSupplierSearch] = useState({ kind: "", loading: false, products: [], message: "", nextOffset: 0, hasMore: false, query: "", category: "" });

  const searchSupplierCatalog = async (kind, append = false) => {
    const query = append ? supplierSearch.query : String(catalogSearch[kind] || "").trim();
    const category = append ? supplierSearch.category : { inverter: "Invertor", panel: "Panou", battery: "Baterie", meter: "Smart meter" }[kind];
    if (query.length < 2) {
      setSupplierSearch({ kind, loading: false, products: [], message: "Introdu cel puțin două caractere din marcă sau model.", nextOffset: 0, hasMore: false, query, category });
      return;
    }
    const offset = append ? supplierSearch.nextOffset : 0;
    setSupplierSearch((previous) => ({ ...previous, kind, loading: true, message: "", query, category }));
    try {
      const { data } = await api.get("/catalog/supplier-search", {
        params: { q: query, category, offset, limit: 24 }, timeout: 60000,
      });
      const products = data.products || [];
      setSupplierSearch((previous) => {
        const seen = new Set(append ? previous.products.map((product) => product.product_url) : []);
        return {
          kind, loading: false,
          products: [...(append ? previous.products : []), ...products.filter((product) => !seen.has(product.product_url))],
          message: data.message || "", nextOffset: Number(data.next_offset) || offset,
          hasMore: Boolean(data.has_more), query, category,
        };
      });
    } catch (error) {
      setSupplierSearch((previous) => ({ ...previous, kind, loading: false, message: error.response?.data?.detail || "Căutarea la furnizori nu este disponibilă momentan." }));
    }
  };

  const importSupplierModel = async (kind, product) => {
    setSupplierSearch((prev) => ({ ...prev, loading: true, message: "" }));
    try {
      const { data } = await api.post("/catalog/supplier-import", {
        supplier: product.supplier, category: product.category, product_url: product.product_url,
      }, { timeout: 60000 });
      let item = data.item;
      if (!item?.id) throw new Error("Produsul nu a putut fi adăugat în catalog.");
      let extractedFields = [];
      let extractionFailed = false;
      if (item.datasheet?.storage_path) {
        setCatalogDocStatus("Fișa PDF a fost importată. Citesc specificațiile modelului pentru completarea dosarului…");
        try {
          const extraction = await api.post(`/ai/catalog/${encodeURIComponent(item.id)}/extract`, {}, { timeout: 35000 });
          extractedFields = Object.keys(extraction.data?.filled || {});
          const refreshed = await api.get("/data/catalog", { timeout: 20000 });
          item = (Array.isArray(refreshed.data) ? refreshed.data : []).find((row) => row.id === item.id) || item;
        } catch {
          // Keep the selected catalog entry and its imported files usable when AI is unavailable.
          extractionFailed = true;
        }
      }
      setCatalog((prev) => [item, ...prev.filter((row) => row.id !== item.id)]);
      choose(kind, item.id, item);
      setCatalogSearch((prev) => ({ ...prev, [kind]: "" }));
      setSupplierSearch({ kind: "", loading: false, products: [], message: "" });
      const importedDocuments = [item.datasheet?.storage_path ? "fișa tehnică" : "", item.conformity?.storage_path ? "declarația de conformitate" : ""].filter(Boolean);
      const extractionNote = extractedFields.length
        ? ` ${extractedFields.length} valori au fost extrase din fișa tehnică și completate numai în câmpurile goale.`
        : extractionFailed ? " Extragerea automată a specificațiilor nu a fost disponibilă; valorile lipsă rămân necompletate." : "";
      setCatalogDocStatus(importedDocuments.length
        ? `Model importat în catalogul firmei; ${importedDocuments.join(" și ")} se atașează la dosar.${extractionNote}`
        : "Model importat în catalogul firmei. Furnizorul nu a oferit documentele în format PDF verificabil; completează-le în Catalog echipamente.");
    } catch (error) {
      setSupplierSearch((prev) => ({ ...prev, loading: false, message: error.response?.data?.detail || error.message || "Modelul nu a putut fi importat." }));
    }
  };

  const addCatalogModel = async (kind, rawName) => {
    const brand_model = String(rawName || "").trim();
    if (!brand_model) return;
    const category = { inverter: "Invertor", panel: "Panou", battery: "Baterie", meter: "Smart meter" }[kind];
    setAddingModel((prev) => ({ ...prev, [kind]: true }));
    try {
      const { data } = await api.post("/data/catalog", { category, brand_model,
        notes: "Adăugat din dosar; completați datele numai din fișa tehnică oficială și declarația de conformitate." });
      setCatalog((prev) => [data, ...prev.filter((item) => item.id !== data.id)]);
      choose(kind, data.id, data);
      setCatalogSearch((prev) => ({ ...prev, [kind]: "" }));
      setProblem("");
    } catch (error) {
      setProblem(error.response?.data?.detail || `Modelul „${brand_model}” nu a putut fi adăugat în catalog.`);
    } finally {
      setAddingModel((prev) => ({ ...prev, [kind]: false }));
    }
  };

  const input = (name, label, type = "text", opts) => (
    <label key={name} className="den-field">
      <span>{label}</span>
      {opts ? <select className="den-input" value={form[name] ?? ""} onChange={(e) => { const v = e.target.value; setVal(name, v); if (name === "supply") setVal("cef", { ...(form.cef || {}), grid: { ...(form.cef?.grid || {}), supply: v } }); }}><option value="">Alege...</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select>
        : <input className="den-input" type={type} step={type === "number" ? "any" : undefined} value={form[name] ?? ""} onChange={(e) => {
          const v = e.target.value; setVal(name, v);
          if (name === "hq_address" && form.address_same_as_ci === true) setVal("address", v);
          if (name === "panel_count") setVal("panel_count_auto", false);
          if (name === "bransament_kw") setVal("cef", { ...(form.cef || {}), grid: { ...(form.cef?.grid || {}), bransament_kw: Number(v) || "" } });
          if (name === "panel_count" && form.cef?.inverters?.length) {
            const inv = { ...form.cef.inverters[0] };
            const strings = inv.strings || [];
            if (!strings.length || strings.every((x) => x.auto_generated)) {
              const proposal = proposeStrings(inv, v);
              inv.strings = proposal || [];
              setVal("cef", { ...form.cef, inverters: [inv, ...form.cef.inverters.slice(1)] });
            }
          }
          if (name === "inverter_count" && form.cef?.inverters?.length) {
            const count = Math.max(1, Number(v) || 1);
            setVal("cef", { ...form.cef, inverters: form.cef.inverters.map((x, i) => i ? x : {
              ...x, count, ...(Number(form.power) > 0 ? { p_limit_kw: Number(form.power) / count } : {}),
            }) });
          }
          if (name === "battery_count" && form.cef?.inverters?.[0]?.battery_mode === "own") {
            const modules = Math.max(1, Number(v) || 1);
            setVal("cef", { ...form.cef, inverters: form.cef.inverters.map((x, i) => i ? x : { ...x, battery: { ...(x.battery || {}), modules } }) });
          }
          if (name === "power") {
            const panel = options.panel.find((x) => x.id === selected.panel);
            const suggestedPanels = form.panel_count_auto === true && panel ? panelCountForPower(v, panel.w) : null;
            if (form.panel_count_auto === true && panel) setVal("panel_count", suggestedPanels);
            if (form.cef?.inverters?.length) {
              const count = Math.max(1, Number(form.inverter_count) || form.cef.inverters.reduce((n, x) => n + (Number(x.count) || 1), 0));
              const nextInverters = form.cef.inverters.map((x, i) => {
                if (i) return x;
                const next = { ...x, p_limit_kw: Number(v) ? Number(v) / count : "" };
                const strings = next.strings || [];
                if ((!strings.length || strings.every((row) => row.auto_generated)) && form.panel_count_auto === true && panel) {
                  next.strings = suggestedPanels ? (proposeStrings(next, suggestedPanels) || []) : [];
                }
                return next;
              });
              setVal("cef", { ...form.cef, inverters: nextInverters });
            }
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
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }}
            disabled={supplierSearch.loading && supplierSearch.kind === kind}
            onClick={() => searchSupplierCatalog(kind)}
            data-testid={`supplier-search-${kind}`}>{supplierSearch.loading && supplierSearch.kind === kind ? "Se caută la furnizori…" : "Caută și în magazine"}</button>
          <span className="text-xs" style={{ color: "var(--muted)" }}>Depozit Solar · SolarHev · SolarTech</span>
        </div>
        {supplierSearch.kind === kind && (supplierSearch.products.length > 0 || supplierSearch.message) && <div className="mt-2 space-y-2 rounded-lg border p-2" style={{ borderColor: "var(--line)" }}>
          {supplierSearch.message && <p className="text-xs" role="status">{supplierSearch.message}</p>}
          {supplierSearch.products.map((product) => <div key={product.product_url} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 p-2">
            <div className="min-w-0"><p className="text-xs font-semibold">{product.brand_model}</p>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>{product.supplier}{product.price_text ? ` · ${product.price_text}` : ""}{product.availability ? ` · ${product.availability}` : ""}</p>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>{product.datasheet_url ? "Fișă PDF" : "Fișă indisponibilă"} · {product.conformity_url ? "conformitate PDF" : "conformitate indisponibilă"}</p></div>
            <button type="button" className="rounded-lg border px-3 py-2 text-xs font-bold" style={{ borderColor: "var(--line)" }}
              disabled={supplierSearch.loading} onClick={() => importSupplierModel(kind, product)}>Importă în catalog și selectează</button>
          </div>)}
        </div>}
        {supplierSearch.kind === kind && supplierSearch.hasMore && <button type="button" className="mt-2 rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }} disabled={supplierSearch.loading} onClick={() => searchSupplierCatalog(kind, true)} data-testid={`supplier-search-more-${kind}`}>{supplierSearch.loading ? "Se încarcă…" : "Încarcă următoarele rezultate"}</button>}
        <select className="den-input" style={selectStyle} value={selected[kind] || ""} onChange={(e) => { choose(kind, e.target.value); setCatalogSearch((prev) => ({ ...prev, [kind]: "" })); }}>
          <option value="">Alege din catalog ({matches.length})...</option>
          {matches.map((x) => <option key={x.id} value={x.id}>{x.brand_model} {x.p_nom_kw ? `· ${x.p_nom_kw} kW` : x.w ? `· ${x.w} W` : x.kwh ? `· ${x.kwh} kWh` : ""}{!(hasStoredCatalogDocument(x, "datasheet") && hasStoredCatalogDocument(x, "conformity")) ? " · PDF-uri de verificat" : ""}</option>)}
        </select>
        {query && matches.length === 0 && <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2">
          <small className="block text-amber-900">Modelul nu există încă în catalog.</small>
          <button type="button" className="mt-1 text-xs font-bold underline disabled:opacity-50" disabled={!!addingModel[kind]}
            onClick={() => addCatalogModel(kind, query)}>{addingModel[kind] ? "Se adaugă…" : `Adaugă „${query.trim()}” în catalog`}</button>
          <small className="mt-1 block text-amber-900">Parametrii și documentele rămân necompletate până la încărcarea fișei oficiale.</small>
        </div>}
        {selected[kind] && (() => { const x = options[kind].find((v) => v.id === selected[kind]); return x && <small className="block mt-1" style={{ color: "var(--muted)" }}>Date preluate din catalog{hasStoredCatalogDocument(x, "datasheet") && hasStoredCatalogDocument(x, "conformity") ? " · PDF-urile sunt atașate" : " · PDF-urile se preiau automat dacă există surse oficiale; verifică documentele lipsă în catalog"}</small>; })()}
      </label>
    );
  };

  return <div className="space-y-4" data-testid="prosumator-quick-form">
    <div className="rounded-2xl border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Dosar prosumator</p>
          <h3 className="mt-1 text-lg font-bold">Date esențiale și echipamente</h3>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>Alege clientul și modelele. Datele disponibile se preiau din dosarul clientului și din catalog.</p></div>
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">Completare asistată</span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="den-field sm:col-span-2"><span>{title(field(cfg, "client_name"), "Beneficiar / client")} *</span>
          <select className="den-input" value={selectedClient?.id || (form.client_name && !clients.some((x) => x.label === form.client_name) ? "__document_import__" : "")} onChange={(e) => {
            const v = e.target.value;
            const c = v === "__document_import__" ? null : clients.find((x) => x.id === v);
            const name = v === "__document_import__" ? form.client_name : (c?.label || "");
            setVal("client_name", name); setVal("client_id", c?.id || "");
            for (const [k, value] of [
              ["cnp", c?.cnp || c?.idcode || ""], ["phone", c?.phone || ""], ["email", c?.email || ""],
              ["hq_address", c?.hq_address || ""], ["address", c?.address || ""], ["county", c?.county || ""],
              ["pod", c?.pod || ""], ["operator", c?.operator || ""], ["cf_nr", c?.cf_nr || ""],
              ["cadastral_nr", c?.cadastral_nr || ""], ["supplier", c?.supplier || ""],
            ]) setVal(k, value);
            setVal("address_same_as_ci", false);
          }}><option value="">Alege client...</option>{form.client_name && !clients.some((x) => x.label === form.client_name) && <option value="__document_import__">{form.client_name} · extras din document</option>}{clients.map((c) => {
            const duplicateName = clients.filter((item) => item.label === c.label).length > 1;
            const detail = c.pod || c.address || ("#" + String(c.id || "").slice(0, 8));
            return <option key={c.id} value={c.id}>{c.label}{duplicateName ? " · " + detail : ""}</option>;
          })}</select>
        </label>
        {input("address", "Adresa locului de consum")}
        {input("pod", "POD")}
        {input("power", "Putere solicitată (kW)", "number")}
      </div>
      <details className="mt-3 rounded-xl border px-3" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer py-3 text-sm font-semibold">Date administrative și branșament</summary>
        <div className="grid gap-3 pb-3 sm:grid-cols-2">
          {input("cnp", "CNP / CUI")}
          {input("phone", "Telefon")}
          {input("email", "Email")}
          {input("hq_address", "Adresă din CI / sediu")}
          {input("request_type", title(field(cfg, "request_type"), "Tip cerere"), "text", field(cfg, "request_type")?.options)}
          {input("operator", "Operator de distribuție", "text", field(cfg, "operator")?.options)}
          {input("supply", title(field(cfg, "supply"), "Branșament"), "text", field(cfg, "supply")?.options)}
          {input("bransament_kw", "Putere branșament (kW)", "number")}
          <label className="den-field sm:col-span-2"><span className="flex items-center gap-2"><input type="checkbox" checked={form.address_same_as_ci === true} onChange={(e) => { setVal("address_same_as_ci", e.target.checked); if (e.target.checked) setVal("address", form.hq_address || ""); }} /> Locul de consum are aceeași adresă ca în CI</span></label>
        </div>
      </details>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>Importă CI, factura și actul de proprietate din zona de documente. Verifică datele extrase automat înainte de salvare.</p>
    </div>

    <div className="rounded-2xl border p-4" style={{ borderColor: "var(--line)", background: "var(--panel)" }}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Configurare</p><h3 className="mt-1 text-lg font-bold">Echipamente și dimensionare</h3></div>
        {catalogLoading ? <span className="text-xs" style={{ color: "var(--muted)" }}>Se încarcă catalogul…</span> : <span className="text-xs" style={{ color: "var(--muted)" }}>{catalog.length} modele în catalog</span>}</div>
      {!!blockedSupplierModels.length && <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="status" data-testid="catalog-supplier-quality-warning">
        {blockedSupplierModels.length} modele importate sunt ascunse din configurare deoarece par pachete cu baterie sau au puterea din denumire diferită de valoarea din catalog. Verifică fișa tehnică și corectează-le în Catalog echipamente înainte de folosire.
        {!!blockedSelectedModels.length && ` Selecția curentă conține ${blockedSelectedModels.length} model/e de verificat.`}
      </p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {catalogSelect("inverter", "Invertor")}
        {input("inverter_count", "Număr invertoare", "number")}
        {catalogSelect("panel", "Panou fotovoltaic")}
        {input("panel_count", form.panel_count_auto === true ? "Număr panouri (calculat)" : "Număr total panouri", "number")}
        {form.panel_count_auto === true && <p className="sm:col-span-2 -mt-2 text-xs text-blue-800">Propunere: puterea solicitată ÷ puterea din fișa panoului, rotunjită în sus. Poți modifica numărul; verifică apoi stringurile și limitele invertorului.</p>}
        {catalogSelect("battery", "Baterie (opțional)")}
        {input("battery_count", "Număr baterii", "number")}
        <label className="den-field"><span>Smart meter</span><span className="flex min-h-10 items-center gap-2"><input type="checkbox" checked={form.smart_meter_present === true} onChange={(e) => {
          const present = e.target.checked;
          setVal("smart_meter_present", present);
          if (!present) {
            setVal("smart_meter_type", "");
            setVal("catalog_selection", { ...selected, meter: "" });
            setVal("cef", { ...(form.cef || {}), grid: { ...(form.cef?.grid || {}), meter: "", meter_catalog_id: "" } });
          }
        }} /> Există la instalație</span></label>
        {form.smart_meter_present === true && catalogSelect("meter", "Model smart meter (opțional)")}
        {catalogDocStatus && <p className="sm:col-span-2 rounded-lg border px-3 py-2 text-xs leading-5" role="status" style={{ borderColor: "var(--line)", color: "var(--muted)", background: "#fff" }}>{catalogDocStatus}</p>}
        <label className="den-field"><span>Backup</span><span className="flex min-h-10 items-center gap-2"><input type="checkbox" checked={form.backup === true || form.backup === "Da"} onChange={(e) => { const on = e.target.checked; setVal("backup", on); setVal("anti_relay_present", on ? "DA" : "NU"); const cef = form.cef || { grid: {}, inverters: [], shared_batteries: [] }; setVal("cef", { ...cef, grid: { ...(cef.grid || {}), anti_required: on }, inverters: (cef.inverters || []).map((x, i) => i ? x : { ...x, backup: { ...(x.backup || {}), enabled: on } }) }); }} /> Include ieșire de rezervă</span></label>
      </div>
      {(() => { const strings = form.cef?.inverters?.[0]?.strings || []; return strings.some((x) => x.auto_generated)
        ? <p className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-900">Propunere stringuri din datele catalogului: {strings.filter((x) => x.auto_generated).map((x, i) => String(i + 1) + "(" + x.panels + ")").join(", ")}. Verifică limitele din manualul exact al echipamentului.</p> : null; })()}
      <details className="mt-3 rounded-xl border px-3" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer py-3 text-sm font-semibold">Verificare documente și date tehnice</summary>
        <div className="space-y-2 pb-3 text-xs" style={{ color: "var(--muted)" }}>
          <p>Datele tehnice selectate sunt preluate din catalog și folosite la generarea schemei. Parametrii care lipsesc nu sunt estimați automat.</p>
          <p>Valorile calculate sunt propuneri pentru verificare; măsurătorile și rezultatele testelor trebuie introduse din documentele reale.</p>
          <p>Variantele cu date cunoscute ca fiind în contradicție cu fișa oficială sunt excluse din configurare. Alege modelul exact al producătorului.</p>
          {problem && <p className="text-amber-700">{problem}</p>}
          {!catalogLoading && catalog.length === 0 && !problem && <p>Catalog gol. Adaugă modele și documente în Catalog echipamente.</p>}
        </div>
      </details>
    </div>
  </div>;
}


