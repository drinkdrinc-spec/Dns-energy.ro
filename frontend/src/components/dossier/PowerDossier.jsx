import { useEffect, useRef, useState } from "react";
import { api, API, downloadAuthenticatedFile, openAuthenticatedFile } from "@/lib/api";
import { uploadFile } from "@/components/dossier/ClientDocs";
import { Btn } from "@/components/Layout";
import { FileText, Plus, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { FormAlert } from "@/components/dossier/FormAlert";

const DOCS = [["a", "Act de identitate / CUI / autorizații de funcționare"], ["b", "Certificat constatator (prosumator PJ)"], ["c", "Certificat de urbanism (loc nou)"],
  ["d", "Plan de situație (loc nou)"], ["e", "PUZ / PUD (loc nou, dacă e cerut)"], ["f", "Act de proprietate / drept de folosință (loc nou)"], ["g", "Autorizație de construire (loc nou)"],
  ["h", "PV recepție instalație de producere"], ["i", "Buletin priză de pământ"], ["j", "Certificate conformitate + fișe tehnice invertoare"], ["k", "Schema monofilară + racordare, protecții, reglaje"]];
const AUTO = { h: "PV recepție", i: "buletin priză", j: "fișe catalog", k: "schemă aprobată" };
const pdf = (id, full) => `/power/${id}/pdf?full=${full}`;

export function Slot({ k, label, files, onChange, auto, autoLabel, testPrefix = "power" }) {
  const ref = useRef();
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs py-1.5 border-t" style={{ borderColor: "var(--line)" }} data-testid={`${testPrefix}-doc-${k}`}>
      <b className="w-20 shrink-0">{k})</b><span className="min-w-[220px] flex-1">{label}</span>
      {files.map((f, i) => <span key={f.storage_path} className="inline-flex items-center gap-1"><button type="button" onClick={() => openAuthenticatedFile(`/files/${f.storage_path}`)} className="underline text-left" style={{ color: "var(--blue)" }}><FileText size={11} className="inline" /> {f.original_filename}</button>
        <button type="button" onClick={() => onChange(files.filter((_, j) => j !== i))}><Trash2 size={11} style={{ color: "#b33333" }} /></button></span>)}
      {!files.length && auto && <span style={{ color: "#166534" }}>auto din dosarul de prosumator: {autoLabel || AUTO[k]}</span>}
      <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={async (e) => { const f = e.target.files?.[0]; if (f) { onChange([...files, await uploadFile(f)]); ref.current.value = ""; } }} />
      <button type="button" className="font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => ref.current.click()} data-testid={`${testPrefix}-upload-${k}`}><Upload size={11} />Încarcă</button>
    </div>
  );
}

export function PowerDossier({ id, form, setVal }) {
  const [pros, setPros] = useState([]);
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); }, []);
  const att = form.attachments || {};
  const recs = form.receptors || [];
  const selectedPros = pros.find((item) => item.id === form.pros_id);
  const operatorLabel = form.operator || selectedPros?.operator || "";
  const isDeer = /\bdeer\b|distributie energie|transilvania|muntenia nord/i.test(operatorLabel);
  const equipment = selectedPros?.cef?.inverters || [];
  const totalPanels = equipment.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, row) => n + (Number(row.panels) || 0), 0) * Math.max(1, Number(inv.count || inv.quantity) || 1), 0);
  const panelKwp = equipment.reduce((sum, inv) => sum + (Number(inv.panel_w) || 0) * (inv.strings || []).reduce((n, row) => n + (Number(row.panels) || 0), 0) * Math.max(1, Number(inv.count || inv.quantity) || 1) / 1000, 0)
    || Number(selectedPros?._kwp || selectedPros?.panel_kwp) || 0;
  const inverterText = equipment.map((inv) => (inv.brand_model || "Invertor") + " × " + Math.max(1, Number(inv.count || inv.quantity) || 1) + " · " + (inv.p_nom_kw || "?") + " kW");
  const batteryItems = [
    ...equipment.filter((inv) => inv.battery_mode === "own" && inv.battery?.model)
      .map((inv) => ({ ...inv.battery, modules: (Number(inv.battery.modules) || 1) * Math.max(1, Number(inv.count || inv.quantity) || 1) })),
    ...(selectedPros?.cef?.shared_batteries || []),
  ];
  const exportLimitKw = equipment.reduce((sum, inv) => {
    const count = Math.max(1, Number(inv.count || inv.quantity) || 1);
    const limit = Number(inv.p_limit_kw) || 0;
    const max = Number(inv.p_max_kw || inv.p_nom_kw) || 0;
    return sum + (limit > 0 ? Math.min(limit, max || limit) * count : 0);
  }, 0);
  useEffect(() => {
    if (!selectedPros) return;
    for (const [key, value] of [["client_name", selectedPros.client_name], ["client_id", selectedPros.client_id],
      ["address", selectedPros.address], ["pod", selectedPros.pod], ["operator", selectedPros.operator],
      ["current_supply", selectedPros.supply || selectedPros.cef?.grid?.supply]]) {
      if (value && !form[key]) setVal(key, value);
    }
  }, [selectedPros?.id]);
  const choosePros = (id) => {
    setVal("pros_id", id);
    const item = pros.find((row) => row.id === id);
    for (const key of ["client_name", "client_id", "address", "pod", "operator", "current_supply"]) {
      const value = key === "current_supply" ? item?.supply || item?.cef?.grid?.supply : item?.[key];
      setVal(key, value || "");
    }
  };
  const setR = (i, k, v) => setVal("receptors", recs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const chk = (k, l, def) => <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={form[k] ?? def ?? false} onChange={(e) => setVal(k, e.target.checked)} data-testid={`power-${k}`} />{l}</label>;
  return (
    <div className="sm:col-span-2 den-panel mt-3" data-testid="power-dossier">
      <FormAlert operator={form.operator} scope="power" />
      <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--blue)" }}>Cerere de racordare — Anexa 1 (Ord. ANRE 69/2020, model DEER) și dosar</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="den-field"><label>Tip cerere</label><select className="den-input" value={form.request_kind || "existent"} onChange={(e) => setVal("request_kind", e.target.value)} data-testid="power-kind">
          <option value="existent">Loc de consum existent — depășirea puterii aprobate</option><option value="nou">Loc de consum și de producere nou</option></select></div>
        <div className="den-field"><label>Dosar de prosumator asociat (date PV + documente automate)</label><select className="den-input" value={form.pros_id || ""} onChange={(e) => choosePros(e.target.value)} data-testid="power-pros">
          <option value="">— fără —</option>{pros.map((p) => <option key={p.id} value={p.id}>{p.number} · {p.client_name}</option>)}</select>
          {selectedPros && <span className="mt-1 block text-[11px]" style={{ color: "var(--muted)" }}>Client, POD, operator și documentele tehnice vor fi preluate din dosarul asociat.</span>}</div>
        <div className="den-field"><label>Putere solicitată (kVA)</label><input className="den-input" value={form.requested_kva || ""} onChange={(e) => setVal("requested_kva", e.target.value)} data-testid="power-kva" /></div>
        <div className="den-field"><label>Data cererii</label><input type="date" className="den-input" value={form.date || ""} onChange={(e) => setVal("date", e.target.value)} data-testid="power-date" /></div>
        {form.request_kind === "nou" && <div className="den-field"><label>Data estimată punere sub tensiune finală</label><input type="date" className="den-input" value={form.energize_date || ""} onChange={(e) => setVal("energize_date", e.target.value)} /></div>}
        <div className="den-field sm:col-span-2"><label>Descrierea modificărilor tehnice față de situația anterioară</label><textarea rows={2} className="den-input" value={form.changes || ""} onChange={(e) => setVal("changes", e.target.value)} data-testid="power-changes" /></div>
      </div>
      {selectedPros && <section className="mt-3 rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="power-linked-equipment">
        <b className="text-xs">Echipamente incluse în Anexa 1</b>
        <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
          <span><b>Invertor:</b> {inverterText.length ? inverterText.join("; ") : "nespecificat"}</span>
          <span><b>Panouri:</b> {selectedPros.panels || "nespecificat"}{totalPanels ? " · " + totalPanels + " buc. · " + panelKwp.toFixed(3) + " kWp DC" : panelKwp ? " · " + panelKwp.toFixed(3) + " kWp DC" : ""}</span>
          <span><b>Limită injecție configurată:</b> {exportLimitKw > 0 ? exportLimitKw.toFixed(3) + " kW AC" : "nedeclarată în setările invertorului"}</span>
          <span><b>Baterie / BESS:</b> {batteryItems.length ? batteryItems.map((item) => (item.model || "model nespecificat") + " × " + (item.modules || 1) + (item.kwh ? " · " + Number(item.kwh) * (Number(item.modules) || 1) + " kWh" : "") + (item.coupling ? " · cuplare " + item.coupling : "")).join("; ") : "nu este selectată"}</span>
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Fișele, declarațiile, PV-ul de recepție, PRAM-ul și schema se atașează la generare când sunt disponibile și validate în dosarul sursă.</p>
      </section>}
      <div className="flex flex-wrap gap-4 mt-3">{chk("ask_atr", "Aviz tehnic de racordare + certificare prosumator", true)}{chk("ask_meter", "Înlocuire contor cu contor bidirecțional")}{chk("ask_probe", "Punere sub tensiune pentru probe")}</div>
      <div className="mt-4 text-xs font-bold">1.3 Lista receptoarelor</div>
      {recs.map((r, i) => <div key={i} className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_90px_minmax(0,1fr)_24px] gap-2 mt-2 sm:mt-1" data-testid={`power-rec-${i}`}>
        <input className="den-input" placeholder="Denumire" value={r.name || ""} onChange={(e) => setR(i, "name", e.target.value)} />
        <input className="den-input" placeholder="kW" value={r.kw || ""} onChange={(e) => setR(i, "kw", e.target.value)} />
        <input className="den-input" placeholder="Observații / regim" value={r.notes || ""} onChange={(e) => setR(i, "notes", e.target.value)} />
        <button type="button" onClick={() => setVal("receptors", recs.filter((_, j) => j !== i))}><Trash2 size={13} style={{ color: "#b33333" }} /></button></div>)}
      <button type="button" className="text-xs font-bold mt-2 inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setVal("receptors", [...recs, {}])} data-testid="power-add-rec"><Plus size={12} />Adaugă receptor</button>
      <div className="mt-4 text-xs font-bold mb-1">Documente anexate</div>
      {DOCS.map(([k, l]) => <Slot key={k} k={k} label={l} files={att[k] || []} auto={!!form.pros_id && AUTO[k]} onChange={(v) => setVal("attachments", { ...att, [k]: v })} />)}
      <div className="flex flex-wrap gap-2 mt-4">
        {id ? <>
          <Btn type="button" variant="secondary" onClick={() => openAuthenticatedFile(pdf(id, 0))} data-testid="power-anexa1-pdf">Anexa 1 model (PDF)</Btn>
          {operatorLabel && <Btn type="button" variant="secondary" onClick={() => downloadAuthenticatedFile(`/power/${id}/official-annex`, isDeer ? "Anexa1_DEER.docx" : "Anexa1_OD")} data-testid="power-official-annex">{isDeer ? "Anexa 1 oficială DEER (DOCX)" : "Formular oficial OD (Anexa 1)"}</Btn>}
          <Btn type="button" onClick={() => openAuthenticatedFile(pdf(id, 1))} data-testid="power-full-pdf">Dosar spor de putere — PDF unic</Btn>
          <Btn type="button" variant="secondary" onClick={() => downloadAuthenticatedFile(`/power/${id}/package.zip`, "Pachet_depunere_spor.zip")} data-testid="power-package">Pachet pentru portal OD (ZIP)</Btn>
        </> : <span className="text-xs" style={{ color: "var(--muted)" }}>Salvați fișa pentru a genera Anexa 1 și dosarul.</span>}
        {id && operatorLabel && !isDeer && <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Formularele PDF se precompletează doar când au câmpuri semantice compatibile; DOCX-ul se descarcă oficial și se verifică manual.</span>}
        {id && <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Salvați modificările înainte de generare.</span>}
      </div>
    </div>
  );
}

export function SimpleDossierBtn({ id }) {
  const url = `/dossier/${id}/simple`;
  return (
    <div className="sm:col-span-2 den-panel mt-3 flex flex-wrap items-center gap-3" data-testid="simple-dossier">
      <div className="flex-1 min-w-[240px]"><b className="text-sm">Dosar de prosumator simplu — PDF unic</b>
        <div className="text-xs" style={{ color: "var(--muted)" }}>Opis + Anexa 2, declarații, împuternicire, buletin PRAM (priză de pământ), schema monofilară, fișa tehnică și fișele echipamentelor. Rămâne CIORNĂ până la completarea datelor și aprobarea schemei.</div></div>
      <Btn type="button" onClick={() => { toast.info("Se generează PDF-ul…"); openAuthenticatedFile(url); }} data-testid="simple-dossier-pdf">Generează dosarul simplu</Btn>
    </div>
  );
}
