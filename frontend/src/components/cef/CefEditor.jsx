import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { GridCard } from "./GridCard";
import { InverterCard } from "./InverterCard";
import { Totals, Issues } from "./CefResults";
import { F, Check, CatalogPick, uid } from "./F";

function SharedBatteries({ list, set, catalog }) {
  const upd = (i, patch) => set(list.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-shared">
      <h4 className="font-bold text-sm mb-1">Baterii comune (folosite de mai multe invertoare)</h4>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Folosește doar dacă arhitectura producătorului permite funcționarea în paralel pe aceeași baterie.</p>
      {list.map((b, i) => (
        <div key={b.id} className="grid sm:grid-cols-4 gap-3 mb-3 pb-3 border-b" style={{ borderColor: "var(--line)" }} data-testid={`shared-${i}`}>
          <CatalogPick items={catalog} category="Baterie" testid={`shared-${i}-pick`} onQueryChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, ah: undefined, voltage: undefined, i_max: undefined, coupling: undefined })} onPick={(it) => upd(i, { catalog_id: it.id, model: it.brand_model, kwh: it.kwh, ah: it.ah, voltage: it.voltage, i_max: it.i_max, coupling: it.coupling || "" })} />
          <F label="Model" value={b.model} onChange={(model) => upd(i, { catalog_id: undefined, model, kwh: undefined, ah: undefined, voltage: undefined, i_max: undefined, coupling: undefined })} testid={`shared-${i}-model`} />
          <F label="kWh / modul" type="number" value={b.kwh} onChange={(v) => upd(i, { kwh: v })} testid={`shared-${i}-kwh`} />
          <F label="Nr. module" type="number" value={b.modules} onChange={(v) => upd(i, { modules: v })} testid={`shared-${i}-modules`} />
          <F label="Ah" type="number" value={b.ah} onChange={(v) => upd(i, { ah: v })} testid={`shared-${i}-ah`} />
          <F label="Tensiune (V)" type="number" value={b.voltage} onChange={(v) => upd(i, { voltage: v })} testid={`shared-${i}-v`} />
          <F label="Curent max descărcare (A)" type="number" value={b.i_max} onChange={(v) => upd(i, { i_max: v })} testid={`shared-${i}-imax`} />
          <F label="Cuplare" value={b.coupling || ""} onChange={(v) => upd(i, { coupling: v })} options={["DC", "AC"]} testid={`shared-${i}-coupling`} />
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
  const set = (patch) => onChange({ ...cef, ...patch });
  const invs = cef.inverters || [];

  useEffect(() => { api.get("/data/catalog").then((r) => setCatalog(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      api.post("/cef/check", { ...cef, tmin: cef.grid?.tmin }).then((r) => setRes(r.data)).catch(() => {});
    }, 500);
    return () => clearTimeout(t);
  }, [JSON.stringify(cef)]); // eslint-disable-line

  const invErrs = new Set((res?.inverters || []).flatMap((i) => [...i.errors, ...i.warnings]));
  return (
    <div className="mt-6 space-y-4" data-testid="cef-editor">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-bold">Configurare CEF — invertoare, stringuri, baterii</h3>
        <button onClick={() => set({ inverters: [...invs, { id: uid(), phases: cef.grid?.supply || "Trifazat", type: "Hibrid", strings: [{ panels: "", mppt: 1 }], battery_mode: "none", ac: { material: "Cu", install: "C" }, dc: { material: "Cu", cable_type: "H1Z2Z2-K" } }] })}
          className="inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold text-white" style={{ background: "var(--blue)" }} data-testid="add-inverter"><Plus size={15} /> Adaugă invertor</button>
      </div>
      <Totals res={res} inverters={invs} />
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
