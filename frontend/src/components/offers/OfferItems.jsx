import { useEffect, useState } from "react";
import { Plus, Trash2, ChevronUp, ChevronDown } from "lucide-react";
import { api } from "@/lib/api";

export const CATS = [["panouri", "Panouri fotovoltaice", "echipament"], ["invertor", "Invertoare", "echipament"], ["baterii", "Baterii", "echipament"],
  ["structura", "Structură montaj (acoperiș / sol / carport)", "echipament"], ["pasive", "Cabluri, conectori, tablouri, protecții AC/DC", "echipament"],
  ["contor", "Contor inteligent / comunicație", "echipament"], ["montaj", "Manoperă, montaj și conexiuni", "serviciu"], ["probe", "Probe, măsurători și PIF", "serviciu"],
  ["proiectare", "Proiectare și asistență tehnică", "serviciu"], ["dosar", "Dosar prosumator / racordare", "serviciu"], ["transport", "Transport", "serviciu"],
  ["mentenanta", "Mentenanță", "serviciu"], ["altele", "Alte servicii", "serviciu"]];
const CATALOG_CAT = { panouri: "Panou", invertor: "Invertor", baterii: "Baterie" };
const SPEC = { panouri: ["power", "Putere panou (W)"], invertor: ["power", "Putere invertor (kW)"], baterii: ["capacity", "Capacitate (kWh)"] };
const W = { name: 150, manufacturer: 100, model: 110, spec: 70, warranty: 80, qty: 55, unit: 50, unit_price: 85 };

export function OfferItems({ items, onChange, currency }) {
  const upd = (i, k, v) => onChange(items.map((it, j) => (j === i ? { ...it, [k]: v } : it)));
  const add = () => onChange([...items, { category: "panouri", kind: "echipament", name: "Panouri fotovoltaice", qty: 1, unit: "buc", unit_price: 0 }]);
  const move = (i, d) => { const a = [...items]; const [x] = a.splice(i, 1); a.splice(i + d, 0, x); onChange(a); };
  const inp = (i, k, w, ph) => <input className="den-input !py-1 !text-xs" style={{ width: w }} placeholder={ph} value={items[i][k] ?? ""} onChange={(e) => upd(i, k, e.target.value)} data-testid={`offer-item-${i}-${k}`} />;
  return (
    <div data-testid="offer-items">
      <div className="space-y-2">{items.map((it, i) => {
        const spec = SPEC[it.category];
        return (
          <div key={i} className="rounded-lg border p-2 bg-white" style={{ borderColor: "var(--line)" }} data-testid={`offer-item-${i}`}>
            <div className="flex flex-wrap items-center gap-1.5">
              <b className="text-xs w-5">{i + 1}.</b>
              <select className="den-input !py-1 !text-xs" style={{ width: 190 }} value={it.category} data-testid={`offer-item-${i}-category`}
                onChange={(e) => { const c = CATS.find((x) => x[0] === e.target.value); onChange(items.map((x, j) => (j === i ? { ...x, category: c[0], kind: c[2], name: x.name && !CATS.some((y) => y[1] === x.name) ? x.name : c[1] } : x))); }}>
                {CATS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
              {CATALOG_CAT[it.category] && <select className="den-input !py-1 !text-xs" style={{ width: 220 }} value={it.catalog_id || ""} onChange={(e) => chooseModel(i, e.target.value)} data-testid={`offer-item-${i}-catalog-model`}>
                <option value="">Alege model din catalog…</option>{choices.map((m) => <option key={m.id} value={m.id}>{m.brand_model}</option>)}
              </select>}
              {inp(i, "name", W.name, "Denumire")}{inp(i, "manufacturer", W.manufacturer, "Producător")}{inp(i, "model", W.model, "Model")}
              {spec && inp(i, spec[0], W.spec, spec[1])}{inp(i, "warranty", W.warranty, "Garanție")}
              {inp(i, "qty", W.qty, "Cant.")}{inp(i, "unit", W.unit, "UM")}{inp(i, "unit_price", W.unit_price, `Preț unitar ${currency}`)}
              <span className="text-xs font-bold ml-1" data-testid={`offer-item-${i}-value`}>{((+String(it.qty).replace(",", ".") || 0) * (+String(it.unit_price).replace(",", ".") || 0)).toFixed(2)}</span>
              <button onClick={() => i > 0 && move(i, -1)} data-testid={`offer-item-${i}-up`}><ChevronUp size={14} /></button>
              <button onClick={() => i < items.length - 1 && move(i, 1)} data-testid={`offer-item-${i}-down`}><ChevronDown size={14} /></button>
              <button onClick={() => onChange(items.filter((_, j) => j !== i))} data-testid={`offer-item-${i}-del`}><Trash2 size={14} style={{ color: "#b33333" }} /></button>
            </div>
            <textarea className="den-input !text-xs mt-1.5" rows={2} placeholder="Descriere (câte un rând per caracteristică)" value={it.description ?? ""} onChange={(e) => upd(i, "description", e.target.value)} data-testid={`offer-item-${i}-description`} />
          </div>);
      })}</div>
      <button className="text-xs font-bold inline-flex items-center gap-1 mt-2" style={{ color: "var(--blue)" }} onClick={add} data-testid="offer-item-add"><Plus size={13} /> Poziție</button>\n      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Modelul poate fi ales din catalog, iar puterea/capacitatea completată automat rămâne editabilă pentru oferta curentă. Prețul și cantitatea se stabilesc separat.</p>
    </div>
  );
}
