import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { ClipboardCheck } from "lucide-react";

const SF = [["voc", "Voc măs. (V)"], ["isc", "Isc măs. (A)"], ["riso_p", "Riso + (MΩ)"], ["riso_n", "Riso − (MΩ)"], ["polarity", "Polaritate"]];
const IF = [["u_ac", "U AC (V)"], ["f_hz", "f (Hz)"], ["p_kw", "P test (kW)"], ["anti_s", "Deconectare (s)"], ["rcd_ms", "DDR (ms)"], ["rcd_ma", "DDR (mA)"]];

export function PifPanel({ id }) {
  const [d, setD] = useState(null);
  const [p, setP] = useState({});
  useEffect(() => { api.get(`/dossier/${id}/pif`).then((r) => { setD(r.data); setP(r.data.pif || {}); }).catch(() => {}); }, [id]);
  if (!d) return null;
  const setIn = (grp, key, f, v) => setP({ ...p, [grp]: { ...(p[grp] || {}), [key]: { ...((p[grp] || {})[key] || {}), [f]: v } } });
  const serials = p.serials || {};
  const setSerial = (group, key, value) => setP({ ...p, serials: { ...serials, [group]: { ...(serials[group] || {}), [key]: value } } });
  const panelSerials = Array.isArray(serials.panels) ? serials.panels.join("\n") : (serials.panels || "");
  const save = async () => { try { const { data } = await api.put(`/dossier/${id}/pif`, p); setP(data.pif); toast.success("Proces-verbal PIF salvat"); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare"); } };
  const cell = (grp, key, f) => <input className="den-input !py-1 text-xs" value={((p[grp] || {})[key] || {})[f] || ""} onChange={(e) => setIn(grp, key, f, e.target.value)} data-testid={`pif-${grp}-${key}-${f}`} />;
  return (
    <div className="sm:col-span-2 den-panel mt-3" data-testid="pif-panel">
      <div className="flex items-center gap-2 mb-2"><ClipboardCheck size={15} style={{ color: "var(--blue)" }} /><b className="text-sm">Proces-verbal de teste și verificări la punerea în funcțiune (PIF)</b></div>
      <p className="text-[11px] mb-3" style={{ color: "var(--muted)" }}>Datele instalației se preiau automat. Rezultatele măsurătorilor se introduc doar după măsurare — câmpurile goale rămân goale în document.</p>
      <div className="grid sm:grid-cols-3 gap-2 mb-3">
        {[["date", "Data testelor", "date"], ["operator", "Executant teste (nume)"], ["instruments", "Aparate (tip, serie, cert. metrologic)"], ["grounding_measured", `Priză de pământ măsurată (Ω)${d.grounding_ohm ? ` — din fișă: ${d.grounding_ohm}` : ""}`]].map(([k, l, t]) => (
          <div key={k} className="den-field"><label>{l}</label><input type={t || "text"} className="den-input" value={p[k] || ""} onChange={(e) => setP({ ...p, [k]: e.target.value })} data-testid={`pif-${k}`} /></div>))}
      </div>
      <div className="overflow-x-auto"><table className="w-full text-xs" data-testid="pif-strings">
        <thead><tr className="text-left" style={{ color: "var(--muted)" }}><th>String</th><th>Voc STC calc.</th>{SF.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>{d.strings.map((s) => <tr key={s.key}><td className="pr-2 py-1">{s.label}</td><td>{s.voc_stc ?? "—"} V</td>{SF.map(([f]) => <td key={f} className="pr-1">{cell("strings", s.key, f)}</td>)}</tr>)}
          {!d.strings.length && <tr><td colSpan={7} className="py-2" style={{ color: "#8a5a00" }}>Stringurile nu sunt definite în configuratorul CEF.</td></tr>}</tbody></table></div>
      <div className="overflow-x-auto mt-3"><table className="w-full text-xs" data-testid="pif-inverters">
        <thead><tr className="text-left" style={{ color: "var(--muted)" }}><th>Invertor</th>{IF.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>{d.inverters.map((v, i) => <tr key={v.n}><td className="pr-2 py-1">INV{v.n} {v.model || ""}</td>{IF.map(([f]) => <td key={f} className="pr-1">{cell("inv", String(i), f)}</td>)}</tr>)}</tbody></table></div>
      <section className="mt-4 rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid="pif-equipment-serials">
        <div className="text-xs font-bold">Serii echipamente montate</div>
        <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Completează seriile citite de pe echipamente la punerea în funcțiune. Sunt opționale pentru pregătirea dosarului și rămân necompletate până la identificarea fizică.</p>
        {d.inverter_units?.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{d.inverter_units.map((unit) => <label key={unit.key} className="den-field"><span>{unit.label}{unit.model ? ` · ${unit.model}` : ""}</span><input className="den-input" value={serials.inverters?.[unit.key] || ""} onChange={(e) => setSerial("inverters", unit.key, e.target.value)} data-testid={`pif-serial-inverter-${unit.key}`} /></label>)}</div>}
        {d.battery_units?.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{d.battery_units.map((unit) => <label key={unit.key} className="den-field"><span>{unit.label}{unit.model ? ` · ${unit.model}` : ""}</span><input className="den-input" value={serials.batteries?.[unit.key] || ""} onChange={(e) => setSerial("batteries", unit.key, e.target.value)} data-testid={`pif-serial-battery-${unit.key}`} /></label>)}</div>}
        {d.panel_count > 0 && <label className="den-field mt-3 block"><span>Serii panouri — una pe rând ({d.panel_count} panouri configurate)</span><textarea rows={Math.min(6, Math.max(2, Math.ceil(d.panel_count / 4)))} className="den-input" value={panelSerials} onChange={(e) => setP({ ...p, serials: { ...serials, panels: e.target.value.split(/\r?\n/) } })} placeholder="Introdu seriile citite de pe etichetele panourilor" data-testid="pif-serial-panels" /></label>}
      </section>
      <div className="mt-3 space-y-1">{d.checks.map((c, k) => (
        <div key={k} className="grid grid-cols-[1fr_150px] gap-2 items-center text-xs"><span>{k + 1}. {c}</span>
          <select className="den-input !py-1 text-xs" value={(p.checks || {})[k] || ""} onChange={(e) => setP({ ...p, checks: { ...(p.checks || {}), [k]: e.target.value } })} data-testid={`pif-check-${k}`}>
            {d.results.map((r) => <option key={r} value={r}>{r || "— neverificat —"}</option>)}</select></div>))}</div>
      <div className="den-field mt-3"><label>Observații</label><textarea rows={2} className="den-input" value={p.notes || ""} onChange={(e) => setP({ ...p, notes: e.target.value })} data-testid="pif-notes" /></div>
      <div className="flex flex-wrap gap-2 mt-3">
        <Btn type="button" onClick={save} data-testid="pif-save">Salvează măsurătorile</Btn>
        <Btn type="button" variant="secondary" onClick={() => openAuthenticatedFile(`/dossier/${id}/pif/pdf`)} data-testid="pif-pdf">Proces-verbal PIF (PDF)</Btn>
      </div>
    </div>
  );
}
