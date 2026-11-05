import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
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

function SharedBatteries({ list, set, catalog }) {
  const upd = (i, patch) => set(list.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-shared">
      <h4 className="font-bold text-sm mb-1">Baterii comune (folosite de mai multe invertoare)</h4>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Folosește doar dacă arhitectura producătorului permite funcționarea în paralel pe aceeași baterie.</p>
      {list.map((b, i) => (
        <div key={b.id} className="grid sm:grid-cols-4 gap-3 mb-3 pb-3 border-b" style={{ borderColor: "var(--line)" }} data-testid={`shared-${i}`}>
          <CatalogPick items={catalog} category="Baterie" testid={`shared-${i}-pick`} onQueryChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, ah: undefined, voltage: undefined, voltage_1ph: undefined, voltage_3ph: undefined, i_max: undefined, i_max_source_url: undefined, max_fuse_a: undefined, coupling: undefined, breaker_a: undefined, breaker_voltage_dc: undefined, breaker_integrated: undefined, breaker_poles: undefined, breaker_icu_ka: undefined, dc_switch_voltage_v: undefined, dc_switch_current_a: undefined, breaker_source_url: undefined, datasheet_url: undefined, conformity_url: undefined })} onPick={(it) => upd(i, sharedBatteryCatalogData(it))} />
          <F label="Model" value={b.model} onChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, ah: undefined, voltage: undefined, voltage_1ph: undefined, voltage_3ph: undefined, i_max: undefined, i_max_source_url: undefined, max_fuse_a: undefined, coupling: undefined, breaker_a: undefined, breaker_voltage_dc: undefined, breaker_integrated: undefined, breaker_poles: undefined, breaker_icu_ka: undefined, dc_switch_voltage_v: undefined, dc_switch_current_a: undefined, breaker_source_url: undefined, datasheet_url: undefined, conformity_url: undefined })} testid={`shared-${i}-model`} />
          <F label="kWh / modul" type="number" value={b.kwh} onChange={(v) => upd(i, { kwh: v })} testid={`shared-${i}-kwh`} />
          <F label="Nr. module" type="number" value={b.modules} onChange={(v) => upd(i, { modules: v })} testid={`shared-${i}-modules`} />
          <F label="Ah" type="number" value={b.ah} onChange={(v) => upd(i, { ah: v })} testid={`shared-${i}-ah`} />
          <F label="Tensiune (V)" type="number" value={b.voltage} onChange={(v) => upd(i, { voltage: v })} testid={`shared-${i}-v`} />
          <F label="Curent max descărcare (A)" type="number" value={b.i_max} onChange={(v) => upd(i, { i_max: v })} testid={`shared-${i}-imax`} />
          <F label="Siguranță max. admisă (A), din fișă" type="number" value={b.max_fuse_a} onChange={(v) => upd(i, { max_fuse_a: v })} testid={`shared-${i}-max-fuse`} />
          <F label="Separator DC: tensiune nominală (V)" type="number" value={b.dc_switch_voltage_v ?? b.breaker_voltage_dc} onChange={(v) => upd(i, { dc_switch_voltage_v: v })} testid={`shared-${i}-dc-switch-voltage`} />
          <F label="Separator DC: curent nominal (A)" type="number" value={b.dc_switch_current_a ?? b.breaker_a} onChange={(v) => upd(i, { dc_switch_current_a: v })} testid={`shared-${i}-dc-switch-current`} />
          <F label="Arhitectură BESS față de sistemul PV" value={b.coupling || ""} onChange={(v) => upd(i, { coupling: v })} options={["DC", "AC"]} testid={`shared-${i}-coupling`} />
          {b.coupling === "AC" && <p className="sm:col-span-4 -mt-2 text-[11px] leading-4" style={{ color: "var(--muted)" }}>Pentru cuplare AC, adaugă un invertor separat de baterie/PCS și leagă această baterie la el. Schema și verificarea rămân incomplete până la selectarea PCS-ului și completarea datelor lui din fișa tehnică.</p>}
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

export function CefEditor({ value, onChange }) {
  const cef = value || { grid: {}, inverters: [], shared_batteries: [] };
  const [catalog, setCatalog] = useState([]);
  const [res, setRes] = useState(null);
  const [supplierCategory, setSupplierCategory] = useState("Invertor");
  const [supplierQuery, setSupplierQuery] = useState("");
  const [supplierResults, setSupplierResults] = useState([]);
  const [supplierMessage, setSupplierMessage] = useState("");
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

  const invErrs = new Set((res?.inverters || []).flatMap((i) => [...i.errors, ...i.warnings]));
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
        {supplierResults.length > 0 && <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {supplierResults.map((product) => <article key={product.product_url} className="rounded-lg border p-2" style={{ borderColor: "var(--line)" }}>
            <p className="text-xs font-semibold">{product.brand_model}</p>
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--muted)" }}>{product.supplier}{product.price_text ? ` · ${product.price_text}` : ""}{product.availability ? ` · ${product.availability}` : ""}</p>
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
      <GridCard grid={cef.grid || {}} set={(g) => set({ grid: g })} catalog={catalog} res={res} />
      {invs.map((inv, i) => (
        <InverterCard key={inv.id || i} idx={i} inv={inv} catalog={catalog} shared={cef.shared_batteries || []} res={res?.inverters?.[i]}
          set={(v) => set({ inverters: invs.map((x, j) => (j === i ? v : x)) })} remove={() => set({ inverters: invs.filter((_, j) => j !== i) })} />
      ))}
      <SharedBatteries list={cef.shared_batteries || []} set={(l) => set({ shared_batteries: l })} catalog={catalog} />
      <Issues errors={(res?.errors || []).filter((e) => !invErrs.has(e))} warnings={(res?.warnings || []).filter((w) => !invErrs.has(w))} testid="cef-global-issues" />
      {res && <p className="text-[11px]" style={{ color: "var(--muted)" }}>{res.note}</p>}
    </div>
  );
}

