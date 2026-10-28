import { useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { lei } from "@/lib/plan";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare");

function PlanRow({ p, features, vat, reload }) {
  const [f, setF] = useState(p);
  const all = f.features.includes("*");
  const tog = (k) => setF({ ...f, features: f.features.includes(k) ? f.features.filter((x) => x !== k) : [...f.features, k] });
  const save = async () => { try { await api.put(`/admin/plans/${p.code}`, { price: f.price, features: f.features, max_inverters: f.max_inverters, name: f.name, description: f.description }); toast.success(`${f.name} salvat`); reload(); } catch (e) { err(e); } };
  const net = Number(f.price || 0);
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }} data-testid={`plan-edit-${p.code}`}>
      <div className="grid sm:grid-cols-4 gap-3">
        <div className="den-field"><label>Denumire</label><input className="den-input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid={`plan-name-${p.code}`} /></div>
        <div className="den-field"><label>Preț lunar fără TVA (lei)</label><input type="number" className="den-input" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid={`plan-price-${p.code}`} /></div>
        <div className="den-field"><label>Max. invertoare / dosar (0 = nelimitat)</label><input type="number" className="den-input" value={f.max_inverters} onChange={(e) => setF({ ...f, max_inverters: e.target.value })} data-testid={`plan-maxinv-${p.code}`} /></div>
        <div className="text-xs self-end pb-2">TVA {vat}%: {lei(net * vat / 100)} · <b>Total {lei(net * (1 + vat / 100))}</b></div>
        <div className="den-field sm:col-span-4"><label>Descriere</label><input className="den-input" value={f.description || ""} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
      </div>
      <div className="flex flex-wrap gap-3 mt-3 text-xs">
        <label className="flex items-center gap-1 font-bold"><input type="checkbox" checked={all} onChange={() => setF({ ...f, features: all ? [] : ["*"] })} data-testid={`plan-all-${p.code}`} /> Toate modulele (inclusiv viitoare)</label>
        {!all && Object.entries(features).map(([k, l]) => <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={f.features.includes(k)} onChange={() => tog(k)} data-testid={`plan-feat-${p.code}-${k}`} />{l}</label>)}
      </div>
      <Btn className="mt-3" onClick={save} data-testid={`plan-save-${p.code}`}>Salvează {f.name}</Btn>
    </div>
  );
}

export function PlanEditor({ data, reload }) {
  const [cfg, setCfg] = useState(data.config);
  const saveCfg = async () => { try { await api.put("/admin/billing-config", { vat_rate: cfg.vat_rate, expired_policy: cfg.expired_policy }); toast.success("Configurare salvată"); reload(); } catch (e) { err(e); } };
  return (
    <div className="space-y-4" data-testid="plan-editor">
      <div className="den-panel flex flex-wrap gap-4 items-end">
        <div className="den-field"><label>Cota TVA (%)</label><input type="number" className="den-input" value={cfg.vat_rate} onChange={(e) => setCfg({ ...cfg, vat_rate: e.target.value })} data-testid="cfg-vat" /></div>
        <div className="den-field"><label>La expirarea abonamentului</label><select className="den-input" value={cfg.expired_policy} onChange={(e) => setCfg({ ...cfg, expired_policy: e.target.value })} data-testid="cfg-policy">
          <option value="read_only">Doar consultare (datele rămân vizibile)</option><option value="blocked">Blocare acces la module (datele se păstrează)</option></select></div>
        <Btn onClick={saveCfg} data-testid="cfg-save">Salvează configurarea</Btn>
      </div>
      {data.plans.map((p) => <PlanRow key={p.code + p.price} p={p} features={data.features} vat={Number(data.config.vat_rate)} reload={reload} />)}
    </div>
  );
}
