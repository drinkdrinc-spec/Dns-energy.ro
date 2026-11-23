import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { supplierPartnerPrice, useSupplierMarkup } from "@/lib/supplierPricing";
import { GridCard } from "./GridCard";
import { InverterCard } from "./InverterCard";
import { Totals, Issues } from "./CefResults";
import { F, Check, CatalogPick, uid } from "./F";

function sharedBatteryCatalogData(item) {
  const breakerCurrent = item.breaker_a ?? item.dc_switch_current_a;
  const breakerVoltage = item.breaker_voltage_dc ?? item.dc_switch_voltage_v;
  return {
    catalog_id: item.id,
    model: item.brand_model,
    kwh: item.kwh,
    tech: item.tech,
    ah: item.ah,
    voltage: item.voltage ?? item.voltage_3ph ?? item.voltage_1ph,
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

function CatalogEquipmentSummary({ item, markup }) {
  if (!item) return null;
  return <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-3 py-2 text-[11px]" style={{ background: "var(--bg, #faf8f4)" }}>
    <span className="font-semibold">{item.brand_model}</span>
    {item.source_price && <span style={{ color: "var(--muted)" }}>Furnizor: {item.source_price}</span>}
    {supplierPartnerPrice(item.source_price, markup) && <span className="font-bold" style={{ color: "var(--green, #168363)" }}>Orientativ DNS (+{markup}%): {supplierPartnerPrice(item.source_price, markup)} / unitate</span>}
    {item.datasheet_url && <a className="font-semibold underline" style={{ color: "var(--green, #168363)" }} href={item.datasheet_url} target="_blank" rel="noopener noreferrer">Fișă tehnică</a>}
    {item.conformity_url && <a className="font-semibold underline" style={{ color: "var(--green, #168363)" }} href={item.conformity_url} target="_blank" rel="noopener noreferrer">Conformitate</a>}
    {!item.datasheet_url && item.datasheet?.storage_path && <span style={{ color: "var(--green, #168363)" }}>Fișa tehnică este salvată în catalog</span>}
    {!item.conformity_url && item.conformity?.storage_path && <span style={{ color: "var(--green, #168363)" }}>Conformitatea este salvată în catalog</span>}
  </div>;
}

function SharedBatteries({ list, set, catalog, supplierMarkup }) {
  const upd = (i, patch) => set(list.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-shared">
      <h4 className="font-bold text-sm mb-1">Baterii comune (folosite de mai multe invertoare)</h4>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Folosește doar dacă arhitectura producătorului permite funcționarea în paralel pe aceeași baterie.</p>
      {list.map((b, i) => (
        <div key={b.id} className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3 pb-3 border-b" style={{ borderColor: "var(--line)" }} data-testid={`shared-${i}`}>
          <div className="col-span-2 sm:col-span-4"><CatalogEquipmentSummary item={catalog.find((item) => item.id === b.catalog_id)} markup={supplierMarkup} /></div>
          <CatalogPick items={catalog} category="Baterie" selectedId={b.catalog_id} testid={`shared-${i}-pick`} onQueryChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, tech: undefined, ah: undefined, voltage: undefined, voltage_1ph: undefined, voltage_3ph: undefined, i_max: undefined, i_max_source_url: undefined, max_fuse_a: undefined, coupling: undefined, breaker_a: undefined, breaker_voltage_dc: undefined, breaker_integrated: undefined, breaker_poles: undefined, breaker_icu_ka: undefined, dc_switch_voltage_v: undefined, dc_switch_current_a: undefined, breaker_source_url: undefined, datasheet_url: undefined, conformity_url: undefined })} onPick={(it) => upd(i, sharedBatteryCatalogData(it))} />
          <F label="Model" value={b.model} onChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, tech: undefined, ah: undefined, voltage: undefined, voltage_1ph: undefined, voltage_3ph: undefined, i_max: undefined, i_max_source_url: undefined, max_fuse_a: undefined, coupling: undefined, breaker_a: undefined, breaker_voltage_dc: undefined, breaker_integrated: undefined, breaker_poles: undefined, breaker_icu_ka: undefined, dc_switch_voltage_v: undefined, dc_switch_current_a: undefined, breaker_source_url: undefined, datasheet_url: undefined, conformity_url: undefined })} testid={`shared-${i}-model`} />
          <F label="kWh / modul" type="number" value={b.kwh} onChange={(v) => upd(i, { kwh: v })} testid={`shared-${i}-kwh`} />
          <F label="Nr. module" type="number" value={b.modules} onChange={(v) => upd(i, { modules: v })} testid={`shared-${i}-modules`} />
          <F label="Ah" type="number" value={b.ah} onChange={(v) => upd(i, { ah: v })} testid={`shared-${i}-ah`} />
          <F label="Tensiune (V)" type="number" value={b.voltage} onChange={(v) => upd(i, { voltage: v })} testid={`shared-${i}-v`} />
          <F label="Curent max descărcare (A)" type="number" value={b.i_max} onChange={(v) => upd(i, { i_max: v })} testid={`shared-${i}-imax`} />
          <F label="Siguranță max. admisă (A), din fișă" type="number" value={b.max_fuse_a} onChange={(v) => upd(i, { max_fuse_a: v })} testid={`shared-${i}-max-fuse`} />
          <F label="Separator DC: tensiune nominală (V)" type="number" value={b.dc_switch_voltage_v ?? b.breaker_voltage_dc} onChange={(v) => upd(i, { dc_switch_voltage_v: v })} testid={`shared-${i}-dc-switch-voltage`} />
          <F label="Separator DC: curent nominal (A)" type="number" value={b.dc_switch_current_a ?? b.breaker_a} onChange={(v) => upd(i, { dc_switch_current_a: v })} testid={`shared-${i}-dc-switch-current`} />
          <F label="Arhitectură BESS față de sistemul PV" value={b.coupling || ""} onChange={(v) => upd(i, { coupling: v })} options={["DC", "AC"]} testid={`shared-${i}-coupling`} />
          {b.coupling === "AC" && <p className="col-span-2 sm:col-span-4 -mt-2 text-[11px] leading-4" style={{ color: "var(--muted)" }}>Pentru cuplare AC, adaugă un invertor separat de baterie/PCS și leagă această baterie la el. Schema și verificarea rămân incomplete până la selectarea PCS-ului și completarea datelor lui din fișa tehnică.</p>}
          <div className="flex items-end gap-3 pb-2">
            <Check label="Producătorul permite paralel" value={b.parallel_supported} onChange={(v) => upd(i, { parallel_supported: v })} testid={`shared-${i}-parallel`} />
            <button onClick={() => set(list.filter((_, j) => j !== i))} data-testid={`shared-${i}-remove`}><Trash2 size={15} style={{ color: "#b33333" }} /></button>
          </div>
        </div>
      ))}
      <button onClick={() => set([...list, { id: uid(), coupling: "", modules: 1 }])} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid="add-shared-battery"><Plus size={13} /> Adaugă baterie comună</button>
    </div>
  );
}

export function CefEditor({ value, onChange, onSave, saving = false }) {
  const cef = value || { grid: {}, inverters: [], shared_batteries: [] };
  const [catalog, setCatalog] = useState([]);
  const [res, setRes] = useState(null);
  const [supplierCategory, setSupplierCategory] = useState("Invertor");
  const [supplierQuery, setSupplierQuery] = useState("");
  const [supplierResults, setSupplierResults] = useState([]);
  const [supplierMessage, setSupplierMessage] = useState("");
  const [supplierMarkup, setSupplierMarkup] = useSupplierMarkup();
  const [supplierBusy, setSupplierBusy] = useState(false);
  const set = (patch) => onChange({ ...cef, ...patch });
  const invs = cef.inverters || [];

  useEffect(() => { api.get("/data/catalog").then((r) => setCatalog(r.data)).catch(() => {}); }, []);

  const searchSuppliers = async () => {
    const query = supplierQuery.trim();
    if (query.length < 2) {
      setSupplierResults([]);
      setSupplierMessage("Introdu cel puțin două caractere din marcă sau model.");
      return;
    }
    setSupplierBusy(true);
    setSupplierMessage("");
    try {
      const { data } = await api.get("/catalog/supplier-search", { params: { q: query, category: supplierCategory }, timeout: 45000 });
      setSupplierResults(data.products || []);
      setSupplierMessage(data.message || "");
    } catch (error) {
      setSupplierResults([]);
      setSupplierMessage(error.response?.data?.detail || "Căutarea la furnizori nu este disponibilă momentan.");
    } finally {
      setSupplierBusy(false);
    }
  };

  const importSupplierProduct = async (product) => {
    setSupplierBusy(true);
    setSupplierMessage("");
    try {
      const { data } = await api.post("/catalog/supplier-import", {
        supplier: product.supplier, category: product.category, product_url: product.product_url,
      }, { timeout: 60000 });
      const item = data.item;
      if (!item?.id) throw new Error("Produsul nu a putut fi adăugat în catalog.");
      setCatalog((previous) => [item, ...previous.filter((row) => row.id !== item.id)]);
      setSupplierResults((previous) => previous.filter((row) => row.product_url !== product.product_url));
      setSupplierMessage(item.datasheet?.storage_path && item.conformity?.storage_path
        ? `${item.brand_model} a fost importat cu fișa și declarația disponibile. Caută-l în selectorul de model.`
        : `${item.brand_model} a fost importat în catalog. Unele documente sau valori tehnice nu sunt publicate ori nu au putut fi preluate; verifică fișa și completează datele lipsă înainte de proiectare.`);
      if (item.datasheet?.storage_path) {
        api.post("/ai/catalog/" + item.id + "/extract")
          .then(({ data: result }) => {
            const count = Object.keys(result?.filled || {}).length;
            setSupplierMessage(count
              ? item.brand_model + ": " + count + " parametri extrași din fișă. Verifică valorile înainte de proiectare."
              : (result?.message || ("Fișa pentru " + item.brand_model + " a fost salvată; nu s-au găsit valori noi.")));
            api.get("/data/catalog").then(({ data: rows }) => setCatalog(rows)).catch(() => {});
          })
          .catch(() => setSupplierMessage("Fișa pentru " + item.brand_model + " a fost salvată, dar extragerea nu a reușit. Modelul poate fi completat ulterior din catalog."));
      }
    } catch (error) {
      setSupplierMessage(error.response?.data?.detail || error.message || "Modelul nu a putut fi importat.");
    } finally {
      setSupplierBusy(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      api.post("/cef/check", { ...cef, tmin: cef.grid?.tmin }).then((r) => setRes(r.data)).catch(() => {});
    }, 500);
    return () => clearTimeout(t);
  }, [JSON.stringify(cef)]); // eslint-disable-line

  // Older and partially configured dossiers may not have per-inverter
  // diagnostics yet. Keep the editor usable while the check endpoint settles.
  const invErrs = new Set((res?.inverters || []).flatMap((i) => [
    ...(Array.isArray(i?.errors) ? i.errors : []),
    ...(Array.isArray(i?.warnings) ? i.warnings : []),
  ]));
  return (
    <div className="mt-6 space-y-4" data-testid="cef-editor">
      <section className="rounded-xl border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid="cef-supplier-lookup">
        <div className="grid gap-2 sm:grid-cols-[180px_1fr_auto] sm:items-end">
          <div className="den-field"><label htmlFor="cef-supplier-category">Categorie echipament</label>
            <select id="cef-supplier-category" className="den-input" value={supplierCategory} onChange={(e) => { setSupplierCategory(e.target.value); setSupplierResults([]); setSupplierMessage(""); }}>
              {["Invertor", "Panou", "Baterie", "Smart meter"].map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </div>
          <div className="den-field"><label htmlFor="cef-supplier-query">Caută modelul la furnizori</label>
            <input id="cef-supplier-query" className="den-input" value={supplierQuery} onChange={(e) => setSupplierQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); searchSuppliers(); } }} placeholder="Marcă sau model..." data-testid="cef-supplier-query" />
          </div>
          <button type="button" className="rounded-lg px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50" style={{ background: "var(--blue)" }}
            onClick={searchSuppliers} disabled={supplierBusy} data-testid="cef-supplier-search">
            {supplierBusy ? "Se caută / importă…" : "Caută la furnizori"}
          </button>
        </div>
        <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Căutare la: Depozit Solar · SolarHev · SolarTech. Importul salvează produsul și PDF-urile disponibile în catalogul firmei.</p>
        {supplierMessage && <p className="mt-2 text-xs" role="status" aria-live="polite">{supplierMessage}</p>}
        <label className="mt-2 inline-flex items-center gap-2 text-[11px] font-semibold">Adaos pentru preț DNS
          <select className="den-input min-h-8 w-20 py-1 text-xs" value={supplierMarkup} onChange={(event) => setSupplierMarkup(Number(event.target.value))} aria-label="Adaos preț DNS">
            <option value={15}>15%</option><option value={20}>20%</option>
          </select>
        </label>
        {supplierResults.length > 0 && <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {supplierResults.map((product) => <article key={product.product_url} className="rounded-lg border p-2" style={{ borderColor: "var(--line)" }}>
            <p className="text-xs font-semibold">{product.brand_model}</p>
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--muted)" }}>{product.supplier}{product.price_text ? ` · ${product.price_text}` : ""}{product.availability ? ` · ${product.availability}` : ""}</p>
            {supplierPartnerPrice(product.price_text, supplierMarkup) && <p className="mt-0.5 text-[11px] font-semibold" style={{ color: "var(--green, #168363)" }}>Preț orientativ DNS (+{supplierMarkup}%): {supplierPartnerPrice(product.price_text, supplierMarkup)} <span className="font-normal">{product.price_tax_note || "TVA de verificat la furnizor"}</span></p>}
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--muted)" }}>{product.datasheet_url ? "Fișă PDF disponibilă" : "Fișă PDF negăsită"} · {product.conformity_url ? "conformitate PDF disponibilă" : "conformitate PDF negăsită"}</p>
            <button type="button" className="mt-2 rounded-md border px-2 py-1.5 text-[11px] font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }}
              onClick={() => importSupplierProduct(product)} disabled={supplierBusy}>Importă în catalog</button>
          </article>)}
        </div>}
      </section>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-bold">Configurare CEF — invertoare, stringuri, baterii</h3>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => set({ inverters: [...invs, { id: uid(), phases: cef.grid?.supply || "Trifazat", type: "Hibrid", strings: [{ panels: "", mppt: 1 }], battery_mode: "none", ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "H1Z2Z2-K" } }] })}
            className="inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold text-white" style={{ background: "var(--blue)" }} data-testid="add-inverter"><Plus size={15} /> Adaugă invertor PV</button>
          <button type="button" onClick={() => {
            const shared = cef.shared_batteries || [];
            const selected = shared.length === 1 ? shared[0] : null;
            set({ inverters: [...invs, { id: uid(), phases: cef.grid?.supply || "Trifazat", type: "Invertor de baterie (AC)", strings: [], battery_mode: selected ? "shared" : "none", ...(selected ? { shared_battery_id: selected.id } : {}), ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "RV-K" } }] });
          }} className="inline-flex items-center gap-2 rounded-[9px] border px-4 py-2.5 text-[12px] font-bold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} data-testid="add-bess-inverter"><Plus size={15} /> Adaugă invertor BESS / PCS AC</button>
        </div>
      </div>
      <Totals res={res} inverters={invs} sharedBatteries={cef.shared_batteries || []} />
      {invs.map((inv, i) => (
        <InverterCard key={inv.id || i} idx={i} inv={inv} catalog={catalog} shared={cef.shared_batteries || []} res={res?.inverters?.[i]} supply={cef.grid?.supply} supplierMarkup={supplierMarkup}
          set={(v) => set({ inverters: invs.map((x, j) => (j === i ? v : x)) })} remove={() => set({ inverters: invs.filter((_, j) => j !== i) })} />
      ))}
      <SharedBatteries list={cef.shared_batteries || []} set={(l) => set({ shared_batteries: l })} catalog={catalog} supplierMarkup={supplierMarkup} />
      <Issues errors={(res?.errors || []).filter((e) => !invErrs.has(e))} warnings={(res?.warnings || []).filter((w) => !invErrs.has(w))} testid="cef-global-issues" />
      {res && <p className="text-[11px]" style={{ color: "var(--muted)" }}>{res.note}</p>}
      <GridCard grid={cef.grid || {}} set={(g) => set({ grid: g })} catalog={catalog} res={res} onSave={onSave} saving={saving} />
    </div>
  );
}

