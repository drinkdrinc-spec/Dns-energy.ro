import { AlertTriangle, XCircle, CheckCircle2 } from "lucide-react";

export function Issues({ errors = [], warnings = [], testid }) {
  if (!errors?.length && !warnings?.length) return null;
  return (
    <div className="mt-3 space-y-1.5" data-testid={testid}>
      {errors.map((e, i) => <div key={`e${i}`} className="flex gap-2 text-xs rounded-lg px-3 py-2" style={{ background: "#fff0f0", color: "#9b2c2c" }}><XCircle size={14} className="shrink-0 mt-0.5" />{e}</div>)}
      {warnings.map((w, i) => <div key={`w${i}`} className="flex gap-2 text-xs rounded-lg px-3 py-2" style={{ background: "#fff8e6", color: "#8a5a00" }}><AlertTriangle size={14} className="shrink-0 mt-0.5" />{w}</div>)}
    </div>
  );
}

export function Totals({ res, grid = {}, inverters = [] }) {
  if (!res) return null;
  const t = res.totals;
  const items = [["Panouri", `${t.kwp} kWp`, "tot-kwp"], ["Invertoare", `${t.inverters_kw} kW`, "tot-kw"], ["Evacuat", `${t.export_kw} kW`, "tot-export"],
    ["Stocare", `${t.storage_kwh} kWh`, "tot-kwh"], ["Nr. panouri", t.panels, "tot-panels"], ["Invertoare", `${t.inverters} buc.`, "tot-inv"]];
  const ok = !res.errors.length && !res.warnings.length;
  return (
    <div className="rounded-xl p-4 text-white" style={{ background: "var(--navy)" }} data-testid="cef-totals">
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        {items.map(([l, v, id]) => (
          <div key={id}><div className="text-[10px] uppercase tracking-wider" style={{ color: "#8fa3c2" }}>{l}</div><div className="font-extrabold text-lg" data-testid={id}>{v}</div></div>
        ))}
      </div>
      <div className="mt-3 text-xs flex items-center gap-2" data-testid="cef-status">
        {ok ? <><CheckCircle2 size={14} color="#4ade80" /> Configurație fără incompatibilități detectate</> :
          <><AlertTriangle size={14} color="#fbbf24" /> {res.errors.length} erori · {res.warnings.length} avertizări</>}
        {res.grid.anti && <span className="ml-2 rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "#7f1d1d" }}>Tablou antiinsularizare inclus</span>}
      </div>
      {res.inverters?.length > 0 && <div className="mt-3 rounded-lg border border-white/15 bg-white/5 p-3" data-testid="cef-auto-sizing">
        <b className="block text-xs">Propuneri automate de protecții și cabluri</b>
        {res.grid?.main_proposal && <p className="mt-2 text-xs">Branșament: disjunctor general propus {res.grid.main_proposal} A · Ib {res.grid.i_br} A.</p>}
        <div className="mt-2 space-y-1.5">
          {res.inverters.map((inv, index) => {
            const ac = inv.proposals?.ac || {};
            const dc = inv.proposals?.dc || {};
            const units = inv.count > 1 ? ` · ${inv.count} buc.` : "";
            return <p key={inv.index || index} className="text-xs leading-relaxed" data-testid={`cef-auto-sizing-${inv.index || index + 1}`}>
              Invertor {inv.index || index + 1}{units}: AC {ac.breaker_a ? `${ac.breaker_a} A` : "protecție nedeterminată"} / {ac.section ? `${ac.section} mm²` : "secțiune nedeterminată"} · DC {dc.section ? `${dc.section} mm²` : "secțiune nedeterminată"}{dc.spd_ucpv ? ` · SPD ${dc.spd_ucpv} V` : ""}{dc.fuse ? ` · gPV ${dc.fuse} A` : ""}
            </p>;
          })}
        </div>
        {inverters.length > 0 && inverters.some((inv) => !Number(inv.ac?.length_m) || !Number(inv.dc?.length_m)) &&
          <p className="mt-2 text-[11px] leading-relaxed text-amber-100">Lungimea unuia sau mai multor trasee nu este introdusă: secțiunile sunt propuneri după curent, iar căderea de tensiune nu este verificată complet. Confirmarea proiectantului autorizat rămâne necesară.</p>}
      </div>}
    </div>
  );
}
