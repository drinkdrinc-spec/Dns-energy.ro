import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const REGLAJ = [["u1", "Tensiune maximală treapta I"], ["u2", "Tensiune minimală treapta II"], ["f1", "Frecvență treapta I"], ["f2", "Frecvență treapta II"],
  ["u10", "Tensiune maximă (medie 10 min)"], ["rec", "Pornire / repornire după întrerupere RED"], ["hvrt", "HVRT"], ["lvrt", "LVRT"], ["droop", "Statism la variația frecvenței"]];
const TYPICAL = { u1: ["1,15 Un", "0,5"], u2: ["0,85 Un", "3,2"], f1: ["52 Hz", "0,5"], f2: ["47,5 Hz", "0,5"], u10: ["253 V", "603"], rec: ["—", "900"], hvrt: ["264,5 V", "Activată"], lvrt: ["184,5 V", "Activată"], droop: ["5 %", "—"] };
const TESTS = [...Array(10).keys()].map((i) => `a${i}`).concat([...Array(4).keys()].map((i) => `f${i}`), [...Array(7).keys()].map((i) => `c${i}`));
const TLABEL = { a: "Test categoria A", f: "Domeniu de frecvență", c: "Verificare" };
const ROLES = [["executant", "Reprezentant executant"], ["resp_tehnic", "Responsabil tehnic cu execuția"], ["electrician", "Electrician autorizat / inginer"],
  ["designer", "Proiectant schemă"], ["verifier", "Verificator schemă"], ["measurer", "Verificator măsurători"]];

const status = (exp, file) => (!file ? "lipsă" : !exp ? "valabil" : exp < new Date().toISOString().slice(0, 10) ? "expirat" : "valabil");
const eligible = (p) => (p.auths || []).some((a) => a.verified && status(a.expires, a.file) === "valabil");

export function DossierExtras({ form, setVal, compact = false }) {
  const [staff, setStaff] = useState([]);
  const [inst, setInst] = useState([]);
  useEffect(() => { api.get("/data/staff").then((r) => setStaff(r.data)).catch(() => {}); api.get("/data/instruments").then((r) => setInst(r.data)).catch(() => {}); }, []);
  const rg = form.reglaj || {}, ts = form.tests || {}, sg = form.signers || {};
  const setR = (k, f, v) => setVal("reglaj", { ...rg, [k]: { ...(rg[k] || {}), [f]: v } });
  const setT = (k, f, v) => setVal("tests", { ...ts, [k]: { ...(ts[k] || {}), [f]: v } });
  return (
    <div className="mt-6 grid lg:grid-cols-2 gap-4" data-testid="dossier-extras">
      <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <h4 className="font-bold text-sm mb-1">{compact ? "DI-U — personal, semnături și aparat PRAM" : "Semnatari și aparat de măsură"}</h4>
        <p className="text-[11px] mb-3" style={{ color: "var(--muted)" }}>
          {compact
            ? "Selectează aici persoanele care vor apărea în documentele DI-U și aparatul folosit pe buletinul de priză de pământ. Salvează dosarul după modificări."
            : "Pot fi alese doar persoanele cu cel puțin o autorizație valabilă, încărcată și marcată „verificată” în Setări de bază."}
        </p>
        {ROLES.map(([k, l]) => (
          <div key={k} className="den-field mb-2"><label>{l}</label>
            <select className="den-input" value={sg[k] || ""} onChange={(e) => setVal("signers", { ...sg, [k]: e.target.value })} data-testid={`signer-${k}`}>
              <option value="">— neselectat —</option>
              {staff.map((p) => <option key={p.id} value={p.id} disabled={!eligible(p)}>{p.name} · {p.qualification || ""}{eligible(p) ? "" : " (autorizație lipsă/expirată/neverificată)"}</option>)}
            </select></div>
        ))}
        <div className="den-field"><label>{compact ? "Aparat PRAM folosit pe buletinul prizei de pământ" : "Aparat de măsură (buletin priză)"}</label>
          <select className="den-input" value={form.instrument_id || ""} onChange={(e) => setVal("instrument_id", e.target.value)} data-testid="instrument-select">
            <option value="">— neselectat —</option>
            {inst.map((i) => <option key={i.id} value={i.id} disabled={status(i.expires, i.file) !== "valabil"}>{i.maker_model} · seria {i.serial} · {i.cert_name} până la {i.expires || "—"}{status(i.expires, i.file) !== "valabil" ? " (expirat / lipsă)" : ""}</option>)}
          </select></div>
      </div>
      {compact && <div className="rounded-lg px-3 py-2 text-[11px] sm:col-span-2" style={{ background: "#fff8e7", color: "#79521a" }}>
        Pentru aplicarea automată a semnăturii instalatorului, în Setări → Personal trebuie să existe o semnătură grafică autorizată; pentru ștampilă, în Setări trebuie încărcată imaginea ștampilei firmei. Dacă lipsesc sau nu sunt autorizate, documentul trebuie semnat olograf — aplicația nu inventează semnături.
      </div>}
      {!compact && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center justify-between mb-2"><h4 className="font-bold text-sm">Buletin reglaj — valori setate în invertor</h4>
          <button className="text-[11px] font-bold" style={{ color: "var(--blue)" }} onClick={() => setVal("reglaj", Object.fromEntries(REGLAJ.map(([k]) => [k, { val: TYPICAL[k][0], t: TYPICAL[k][1] }])))} data-testid="reglaj-typical">Preia valorile tip Ord. ANRE 132/2020 (verifică în invertor)</button></div>
        {REGLAJ.map(([k, l]) => (
          <div key={k} className="grid grid-cols-[1fr_90px_80px] gap-2 mb-1.5 items-center text-xs"><span>{l}</span>
            <input className="den-input py-1" placeholder="valoare" value={rg[k]?.val || ""} onChange={(e) => setR(k, "val", e.target.value)} data-testid={`reglaj-${k}-val`} />
            <input className="den-input py-1" placeholder="timp (s)" value={rg[k]?.t || ""} onChange={(e) => setR(k, "t", e.target.value)} data-testid={`reglaj-${k}-t`} /></div>
        ))}
      </div>}
      {!compact && <div className="rounded-xl border p-4 bg-white lg:col-span-2" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2"><h4 className="font-bold text-sm">Teste și verificări PIF (Ord. ANRE 228/2018) — rezultate</h4>
          <button className="text-[11px] font-bold" style={{ color: "var(--blue)" }} onClick={() => setVal("tests", Object.fromEntries(TESTS.map((k) => [k, { ...(ts[k] || {}), ok: ts[k]?.ok || "DA" }])))} data-testid="tests-all-da">Marchează DA pe rândurile necompletate (doar dacă e confirmat de certificatul de tip)</button></div>
        <div className="grid sm:grid-cols-3 gap-2">
          {TESTS.map((k) => (
            <div key={k} className="flex items-center gap-2 text-xs"><span className="w-28 shrink-0">{TLABEL[k[0]]} {Number(k.slice(1)) + 1}</span>
              <select className="den-input py-1 w-20" value={ts[k]?.ok || ""} onChange={(e) => setT(k, "ok", e.target.value)} data-testid={`test-${k}`}><option value="">—</option><option>DA</option><option>NU</option></select>
              <input className="den-input py-1" placeholder="observații / valori" value={ts[k]?.obs || ""} onChange={(e) => setT(k, "obs", e.target.value)} data-testid={`test-${k}-obs`} /></div>
          ))}
        </div>
      </div>}
    </div>
  );
}
