import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { GridCard } from "./GridCard";
import { InverterCard } from "./InverterCard";
import { Totals, Issues } from "./CefResults";
import { F, Check, CatalogPick, uid } from "./F";

const step = (values, min) => values.find((value) => value >= Number(min)) || null;

function applyDefaultRecommendations(cef, check) {
  const filled = [];
  const put = (obj, key, value, path) => {
    if (value !== undefined && value !== null && value !== "" && (obj[key] === undefined || obj[key] === null || obj[key] === "")) {
      obj[key] = value;
      filled.push(path);
    }
  };
  const inverters = (cef.inverters || []).map((source, i) => {
    const inv = { ...source, ac: { ...(source.ac || {}) }, dc: { ...(source.dc || {}) } };
    const result = check.inverters?.[i];
    if (!result) return inv;
    const ac = result.proposals?.ac || {};
    const dc = result.proposals?.dc || {};
    const prefix = `cef.inverters.${i}`;
    put(inv.ac, "breaker_a", ac.breaker_a, `${prefix}.ac.breaker_a`);
    put(inv.ac, "section", ac.section, `${prefix}.ac.section`);
    const acSection = Number(inv.ac.section);
    const peSection = acSection <= 16 ? acSection : acSection <= 35 ? 16 : step([1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240], acSection / 2);
    if (acSection > 0) put(inv.ac, "pe_section", peSection, `${prefix}.ac.pe_section`);
    if (result.strings?.length) {
      put(inv.dc, "cable_type", "H1Z2Z2-K", `${prefix}.dc.cable_type`);
      put(inv.dc, "section", dc.section, `${prefix}.dc.section`);
      put(inv.dc, "spd_ucpv", dc.spd_ucpv, `${prefix}.dc.spd_ucpv`);
      put(inv.dc, "fuse_a", dc.fuse, `${prefix}.dc.fuse_a`);
      const switchVoltage = Number(result.voc_cold_max) > 0 ? step([600, 800, 1000, 1100, 1200, 1500], result.voc_cold_max) : null;
      const switchCurrent = Number(result.isc_mppt_max) > 0 ? step([16, 20, 25, 32, 40, 50, 63, 80, 100, 125], 1.25 * Number(result.isc_mppt_max)) : null;
      if (switchVoltage && switchCurrent) put(inv.dc, "switch", `${switchVoltage} V / ${switchCurrent} A DC-PV2`, `${prefix}.dc.switch`);
    }
    if (inv.battery_mode === "own" && inv.battery) {
      const battery = { ...inv.battery };
      if (Number(battery.i_max) > 0) put(battery, "fuse_a", step([32, 40, 50, 63, 80, 100, 125, 160, 200, 250], 1.25 * Number(battery.i_max)), `${prefix}.battery.fuse_a`);
      inv.battery = battery;
    }
    return inv;
  });
  const grid = { ...(cef.grid || {}) };
  const tri = check.grid?.tri !== false;
  const main = check.grid?.main_proposal;
  put(grid, "bmp_a", main, "cef.grid.bmp_a");
  put(grid, "tg_breaker_a", main, "cef.grid.tg_breaker_a");
  put(grid, "rcd_ma", 30, "cef.grid.rcd_ma");
  put(grid, "spd_ac", `SPD ${tri ? "4P" : "2P"} · Tip 2 · Up 1,5 kV`, "cef.grid.spd_ac");
  if (grid.tg_breaker_a) put(grid, "tg_general", `${grid.tg_breaker_a} A ${tri ? "4P" : "2P"} dif. ${grid.rcd_ma || 30} mA`, "cef.grid.tg_general");
  const dcValues = (check.inverters || []).flatMap((result, i) => result.strings?.length && result.proposals?.dc?.spd_ucpv
    ? [{ inverter: i + 1, voltage: result.proposals.dc.spd_ucpv, section: result.proposals.dc.section }]
    : []);
  if (dcValues.length) {
    put(grid, "spd_dc", dcValues.map((x) => `INV ${x.inverter}: ${x.voltage} V`).join(" · "), "cef.grid.spd_dc");
    const sections = dcValues.filter((x) => x.section).map((x) => `INV ${x.inverter}: ${x.section} mm²`);
    if (sections.length) put(grid, "solar_cable", `H1Z2Z2-K · ${sections.join(" · ")} (secțiuni propuse)`, "cef.grid.solar_cable");
  }
  if (!filled.length) return cef;
  return { ...cef, inverters, grid, auto_filled: [...new Set([...(cef.auto_filled || []), ...filled])].sort() };
}

function SharedBatteries({ list, set, catalog }) {
  const upd = (i, patch) => set(list.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-shared">
      <h4 className="font-bold text-sm mb-1">Baterii comune (folosite de mai multe invertoare)</h4>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Folosește doar dacă arhitectura producătorului permite funcționarea în paralel pe aceeași baterie.</p>
      {list.map((b, i) => (
        <div key={b.id} className="grid sm:grid-cols-4 gap-3 mb-3 pb-3 border-b" style={{ borderColor: "var(--line)" }} data-testid={`shared-${i}`}>
          <CatalogPick items={catalog} category="Baterie" selectedId={b.catalog_id} testid={`shared-${i}-pick`} onPick={(it) => upd(i, { catalog_id: it.id, model: it.brand_model, kwh: it.kwh, ah: it.ah, voltage: it.voltage, voltage_min: it.voltage_min, voltage_max: it.voltage_max, voltage_ranges: it.voltage_ranges || [], i_max: it.i_max, tech: it.tech, spec_source_url: it.spec_source_url || "", coupling: it.coupling || "DC" })} />
          <F label="Model" value={b.model} onChange={(v) => upd(i, { model: v })} testid={`shared-${i}-model`} />
          <F label="kWh / modul" type="number" value={b.kwh} onChange={(v) => upd(i, { kwh: v })} testid={`shared-${i}-kwh`} />
          <F label="Nr. module" type="number" value={b.modules} onChange={(v) => upd(i, { modules: v })} testid={`shared-${i}-modules`} />
          <F label="Ah" type="number" value={b.ah} onChange={(v) => upd(i, { ah: v })} testid={`shared-${i}-ah`} />
          <F label="Tensiune (V)" type="number" value={b.voltage} onChange={(v) => upd(i, { voltage: v })} testid={`shared-${i}-v`} />
          <F label="Curent max descărcare (A)" type="number" value={b.i_max} onChange={(v) => upd(i, { i_max: v })} testid={`shared-${i}-imax`} />
          <F label="Cuplare" value={b.coupling || "DC"} onChange={(v) => upd(i, { coupling: v })} options={["DC", "AC"]} testid={`shared-${i}-coupling`} />
          <div className="flex items-end gap-3 pb-2">
            <Check label="Producătorul permite paralel" value={b.parallel_supported} onChange={(v) => upd(i, { parallel_supported: v })} testid={`shared-${i}-parallel`} />
            <button onClick={() => set(list.filter((_, j) => j !== i))} data-testid={`shared-${i}-remove`}><Trash2 size={15} style={{ color: "#b33333" }} /></button>
          </div>
        </div>
      ))}
      <button onClick={() => set([...list, { id: uid(), coupling: "DC", modules: 1 }])} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid="add-shared-battery"><Plus size={13} /> Adaugă baterie comună</button>
    </div>
  );
}

function AuxiliaryEquipment({ list, set, catalog }) {
  const update = (idx, patch) => set(list.map((item, i) => i === idx ? { ...item, ...patch } : item));
  return <section className="rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }} data-testid="cef-auxiliary-equipment">
    <div className="mb-3"><h4 className="text-sm font-bold">Gateways și optimizatoare</h4><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Alege echipamentele din catalog; fișele lor se pot include în dosarul PDF.</p></div>
    <div className="space-y-3">
      {list.map((item, idx) => <div key={item.id || idx} className="grid items-end gap-3 border-b pb-3 sm:grid-cols-[150px_minmax(0,1fr)_100px_auto]" style={{ borderColor: "var(--line)" }} data-testid={`cef-aux-item-${idx}`}>
        <F label="Categorie" value={item.category} options={[["Gateway", "Gateway"], ["Optimizator", "Optimizator"]]} onChange={(category) => update(idx, { category, catalog_id: "", model: "" })} testid={`cef-aux-category-${idx}`} />
        <CatalogPick items={catalog} category={item.category || "Gateway"} selectedId={item.catalog_id} label="Dispozitiv din catalog" testid={`cef-aux-pick-${idx}`} onPick={(device) => update(idx, { catalog_id: device.id, model: device.brand_model, datasheet: !!device.datasheet, conformity: !!device.conformity })} />
        <F label="Cantitate" type="number" value={item.quantity || 1} onChange={(quantity) => update(idx, { quantity })} testid={`cef-aux-quantity-${idx}`} />
        <button onClick={() => set(list.filter((_, i) => i !== idx))} className="mb-2 rounded p-2 hover:bg-red-50" aria-label="Elimină dispozitivul" data-testid={`cef-aux-remove-${idx}`}><Trash2 size={15} style={{ color: "#b33333" }} /></button>
        {item.model && <div className="sm:col-start-2 sm:col-span-2 -mt-2 text-[10px]" style={{ color: item.datasheet && item.conformity ? "var(--green)" : "#b9770e" }}>{item.model} · {item.datasheet && item.conformity ? "documente complete" : "verifică fișa și conformitatea în catalog"}</div>}
      </div>)}
    </div>
    <button onClick={() => set([...list, { id: uid(), category: "Gateway", quantity: 1 }])} className="mt-3 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--green)" }} data-testid="cef-aux-add"><Plus size={14} /> Adaugă gateway sau optimizator</button>
  </section>;
}

export function CefEditor({ value, onChange, groundingOhm, groundingLimit, boardsOnly = false }) {
  const cef = value || { grid: {}, inverters: [], shared_batteries: [] };
  const [catalog, setCatalog] = useState([]);
  const [res, setRes] = useState(null);
  const [sizingRules, setSizingRules] = useState(null);
  const set = (patch) => onChange({ ...cef, ...patch });
  const invs = cef.inverters || [];

  useEffect(() => { api.get("/data/catalog").then((r) => setCatalog(r.data)).catch(() => {}); api.get("/settings").then((r) => setSizingRules(r.data.sizing_rules || null)).catch(() => {}); }, []);
  useEffect(() => {
    let active = true;
    const snapshot = cef;
    const t = setTimeout(() => {
      api.post("/cef/check", { ...snapshot, recommendations: sizingRules, tmin: snapshot.grid?.tmin })
        .then((r) => {
          if (!active) return;
          setRes(r.data);
          const updated = applyDefaultRecommendations(snapshot, r.data);
          if (updated !== snapshot) onChange(updated);
        }).catch(() => {});
    }, 500);
    return () => { active = false; clearTimeout(t); };
  }, [JSON.stringify(cef), JSON.stringify(sizingRules)]); // eslint-disable-line

  const invErrs = new Set((res?.inverters || []).flatMap((i) => [...i.errors, ...i.warnings]));
  return (
    <div className="mt-6 space-y-4" data-testid="cef-editor">
      {!boardsOnly && <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-bold">Configurare CEF — invertoare, stringuri, baterii</h3>
        <button onClick={() => set({ inverters: [...invs, { id: uid(), phases: cef.grid?.supply || "Trifazat", type: "Hibrid", strings: [{ panels: "", mppt: 1 }], battery_mode: "none", ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "H1Z2Z2-K" } }] })}
          className="inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold text-white" style={{ background: "var(--blue)" }} data-testid="add-inverter"><Plus size={15} /> Adaugă invertor</button>
      </div>}
      {!boardsOnly && <div className="rounded-xl border bg-white px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <Check label="Extindere CEF existentă (instalația veche rămâne în funcțiune)" value={cef.existing_extension} onChange={(v) => set({ existing_extension: v })} testid="cef-existing-extension" />
      </div>}
      {!boardsOnly && <Totals res={res} />}
      {!boardsOnly && invs.map((inv, i) => (
        <InverterCard key={inv.id || i} idx={i} inv={inv} catalog={catalog} shared={cef.shared_batteries || []} res={res?.inverters?.[i]}
          set={(v) => set({ inverters: invs.map((x, j) => (j === i ? v : x)) })} remove={() => set({ inverters: invs.filter((_, j) => j !== i) })} />
      ))}
      <GridCard grid={cef.grid || {}} set={(g) => set({ grid: g })} catalog={catalog} res={res} inverters={invs} groundingOhm={groundingOhm} groundingLimit={groundingLimit} showIntro={!boardsOnly} />
      <details className="rounded-xl border bg-white px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer text-sm font-bold">Alte detalii tehnice (opțional)</summary>
        <div className="mt-3 space-y-4">
          <SharedBatteries list={cef.shared_batteries || []} set={(l) => set({ shared_batteries: l })} catalog={catalog} />
          <AuxiliaryEquipment list={cef.auxiliary_equipment || []} set={(l) => set({ auxiliary_equipment: l })} catalog={catalog} />
          <Issues errors={(res?.errors || []).filter((e) => !invErrs.has(e))} warnings={(res?.warnings || []).filter((w) => !invErrs.has(w))} testid="cef-global-issues" />
        </div>
      </details>
      {res && <p className="text-[11px]" style={{ color: "var(--muted)" }}>{res.note}</p>}
    </div>
  );
}

