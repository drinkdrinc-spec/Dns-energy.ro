import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const REGLAJ = [["u1", "Tensiune maximală treapta I"], ["u2", "Tensiune minimală treapta II"], ["f1", "Frecvență treapta I"], ["f2", "Frecvență treapta II"],
  ["u10", "Tensiune maximă (medie 10 min)"], ["rec", "Pornire / repornire după întrerupere RED"], ["hvrt", "HVRT"], ["lvrt", "LVRT"], ["droop", "Statism la variația frecvenței"]];
const TYPICAL = { u1: ["1,15 Un", "0,5"], u2: ["0,85 Un", "3,2"], f1: ["52 Hz", "0,5"], f2: ["47,5 Hz", "0,5"], u10: ["253 V", "603"], rec: ["—", "900"], hvrt: ["264,5 V", "Activată"], lvrt: ["184,5 V", "Activată"], droop: ["5 %", "—"] };
const TESTS = [...Array(10).keys()].map((i) => `a${i}`).concat([...Array(4).keys()].map((i) => `f${i}`), [...Array(7).keys()].map((i) => `c${i}`));
const TLABEL = { a: "Test categoria A", f: "Domeniu de frecvență", c: "Verificare" };

export function DossierExtras({ form, setVal, compact = false, part = "all", onSave, saving = false, dossierId }) {
  const pramInput = useRef(null);
  const [pramBusy, setPramBusy] = useState(false);
  const [pramNumberBusy, setPramNumberBusy] = useState(false);
  const [staff, setStaff] = useState([]);
  const [instruments, setInstruments] = useState([]);
  useEffect(() => { api.get("/data/staff").then(({ data }) => setStaff(Array.isArray(data) ? data : [])).catch(() => setStaff([])); }, []);
  useEffect(() => { api.get("/data/instruments").then(({ data }) => setInstruments(Array.isArray(data) ? data : [])).catch(() => setInstruments([])); }, []);
  const selectedExecutor = form.signers?.executant || "";
  const today = new Date().toISOString().slice(0, 10);
  const eligible = (person) => (person.auths || []).some((auth) => auth.verified && auth.file && (!auth.expires || auth.expires >= today));
  const chooseExecutor = (id) => setVal("signers", { ...(form.signers || {}), executant: id || null });
  const allocatePramNumber = async () => {
    if (!dossierId || pramNumberBusy) return;
    setPramNumberBusy(true);
    try {
      const { data } = await api.post(`/prosumator/${encodeURIComponent(dossierId)}/pram-number`);
      setVal("bulletin_no", data.number);
      toast.success(`Buletin PRAM nr. ${data.number} alocat din seria firmei.`);
    } catch (error) { toast.error(error.response?.data?.detail || "Nu am putut aloca numărul PRAM."); }
    finally { setPramNumberBusy(false); }
  };
  const rg = form.reglaj || {}, ts = form.tests || {};
  const setR = (k, f, v) => setVal("reglaj", { ...rg, [k]: { ...(rg[k] || {}), [f]: v }, verified_by_installer: false });
  const reglajValuesComplete = REGLAJ.every(([k]) => String(rg[k]?.val || "").trim() && String(rg[k]?.t || "").trim());
  const setT = (k, f, v) => setVal("tests", { ...ts, [k]: { ...(ts[k] || {}), [f]: v } });
  return (
    <div id={compact ? "diu-executant" : undefined} className="mt-6 grid lg:grid-cols-2 gap-4" data-testid="dossier-extras">
      {part !== "commissioning" && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="dossier-executant-signer">
        <h4 className="font-bold text-sm mb-2">Semnătura și ștampila firmei</h4>
        <label className="den-field block"><span className="text-xs">Reprezentant executant</span>
          <select className="den-input" value={selectedExecutor} onChange={(event) => chooseExecutor(event.target.value)} data-testid="dossier-executant-select">
            <option value="">Alege persoana din Setări → Personal</option>
            {staff.map((person) => <option key={person.id} value={person.id} disabled={!eligible(person)}>
              {person.name || "Persoană fără nume"}{eligible(person) ? "" : " — autorizație neconfirmată"}
            </option>)}
          </select>
        </label>
        <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Pentru aplicare: încarcă ștampila în Setări → Firmă și semnătura persoanei în Setări → Personal, confirmă autorizația și acordul pentru folosirea semnăturii. Salvează dosarul după selectare.</p>
      </div>}
      {!compact && (part === "all" || part === "pram") && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center justify-between gap-2"><h4 className="font-bold text-sm">PRAM — priza de pământ</h4><span className="text-xs" style={{ color: "var(--muted)" }}>{form.bulletin_no ? `Buletin nr. ${form.bulletin_no}` : "număr de completat"}</span></div>
        <div className="mt-3 grid grid-cols-3 rounded-lg p-1 gap-1" style={{ background: "#f7f4ed" }} role="group" aria-label="Sursa buletinului PRAM">
          {[["internal", "Îl fac eu"], ["third_party", "Buletin de la terț"], ["none", "Fără PRAM"]].map(([value, label]) => <button key={value} type="button" onClick={() => setVal("pram_source", value)} className="rounded-md px-2 py-2 text-xs font-semibold" style={{ background: (form.pram_source || "internal") === value ? "#fff" : "transparent", color: (form.pram_source || "internal") === value ? "var(--green)" : "var(--muted)", boxShadow: (form.pram_source || "internal") === value ? "0 1px 4px #0001" : "none" }} data-testid={`pram-mode-${value}`}>{label}</button>)}
        </div>
        {(!form.pram_source || form.pram_source === "internal") && <>
          <div className="mt-3 rounded-lg px-3 py-2 text-xs font-semibold" style={{ background: "#edf7f0", color: "#287347" }}>Buletin nr. {form.bulletin_no || "—"} · numerotare din seria firmei</div>
          <div className="mt-3 grid sm:grid-cols-2 gap-3">
            <label className="den-field"><span>Nr. buletin</span><div className="flex gap-2"><input className="den-input min-w-0" value={form.bulletin_no || ""} onChange={(e) => setVal("bulletin_no", e.target.value)} placeholder="Număr din registrul firmei" data-testid="pram-number" />{dossierId && !form.bulletin_no && <button type="button" className="shrink-0 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)", color: "var(--green)" }} onClick={allocatePramNumber} disabled={pramNumberBusy} data-testid="pram-number-next">{pramNumberBusy ? "…" : "Următorul nr."}</button>}</div></label>
            <label className="den-field"><span>Data măsurătorii</span><input className="den-input" type="date" value={form.measure_date || ""} onChange={(e) => setVal("measure_date", e.target.value)} data-testid="pram-date" /></label>
            <label className="den-field"><span>Starea solului</span><select className="den-input" value={form.soil || ""} onChange={(e) => { const psi = { "sol uscat": "1.5", "umiditate medie": "1.3", "sol umed": "1.1" }[e.target.value]; setVal("soil", e.target.value); if (psi) setVal("soil_psi", psi); }} data-testid="pram-soil"><option value="">Alege…</option><option>sol uscat</option><option>umiditate medie</option><option>sol umed</option></select></label>
            <label className="den-field"><span>Coeficient Ψ</span><input className="den-input" type="number" step="0.001" value={form.soil_psi ?? ""} onChange={(e) => setVal("soil_psi", e.target.value)} data-testid="pram-psi" /></label>
            <label className="den-field"><span>Rezistență măsurată (Ω)</span><input className="den-input" type="number" step="0.01" value={form.grounding_ohm ?? ""} onChange={(e) => setVal("grounding_ohm", e.target.value)} data-testid="pram-measured" /></label>
            <label className="den-field"><span>Valoare admisă (Ω)</span><input className="den-input" type="number" step="0.01" value={form.grounding_limit ?? ""} onChange={(e) => setVal("grounding_limit", e.target.value)} data-testid="pram-limit" /></label>
            <label className="den-field"><span>Obiectivul verificării</span><input className="den-input" value={form.measure_object || ""} onChange={(e) => setVal("measure_object", e.target.value)} placeholder="Priza de pământ a instalației" data-testid="pram-object" /></label>
            <label className="den-field"><span>Aparat de măsură</span><select className="den-input" value={form.instrument_id || ""} onChange={(e) => setVal("instrument_id", e.target.value)} data-testid="pram-instrument"><option value="">Alege din Setări → Aparate de măsură</option>{instruments.map((instrument) => <option key={instrument.id} value={instrument.id}>{instrument.maker_model || instrument.name || instrument.model || "Aparat"}{instrument.serial ? ` · ${instrument.serial}` : ""}{instrument.expires ? ` · valabil până la ${instrument.expires}` : ""}</option>)}</select></label>
          </div>
          {form.grounding_ohm && form.soil_psi && <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>Valoare corectată după coeficientul Ψ: <b>{(Number(String(form.grounding_ohm).replace(",", ".")) * Number(String(form.soil_psi).replace(",", "."))).toFixed(2)} Ω</b></p>}
          <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Aparatul selectat aduce în dosar certificatul metrologic. Rezultatul și data se introduc numai după măsurare.</p>
        </>}
        {form.pram_source === "third_party" && <div className="text-xs">
          <input ref={pramInput} type="file" accept="application/pdf,.pdf" className="hidden" data-testid="pram-upload-input"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (!file.name.toLowerCase().endsWith(".pdf")) { toast.error("Încarcă buletinul PRAM în format PDF."); event.target.value = ""; return; }
              setPramBusy(true);
              try {
                const body = new FormData(); body.append("file", file);
                const { data } = await api.post("/upload", body, { headers: { "Content-Type": "multipart/form-data" } });
                setVal("pram_file", data);
                toast.success("Buletinul PRAM terț a fost atașat.");
              } catch (error) {
                toast.error(error.response?.data?.detail || "Nu am putut încărca buletinul PRAM.");
              } finally { setPramBusy(false); event.target.value = ""; }
            }} />
          <button type="button" className="den-input text-left" disabled={pramBusy} onClick={() => pramInput.current?.click()} data-testid="pram-upload">
            {pramBusy ? "Se încarcă…" : form.pram_file?.original_filename || "Alege PDF-ul buletinului PRAM"}
          </button>
          {form.pram_file?.storage_path && <button type="button" className="ml-2 underline" style={{ color: "var(--blue)" }}
            onClick={() => setVal("pram_file", null)} data-testid="pram-remove">Elimină</button>}
        </div>}
        {form.pram_source === "none" && <p className="mt-3 rounded-lg p-3 text-xs" style={{ background: "#f7f4ed", color: "var(--muted)" }}>Buletinul PRAM și metrologia nu vor fi incluse în pachetul generat. Verifică dacă operatorul le cere pentru acest dosar.</p>}
        {onSave && <div className="mt-4 flex justify-end"><button type="button" className="rounded-lg px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60" style={{ background: "var(--green)" }} onClick={onSave} disabled={saving} data-testid="save-pram-card">{saving ? "Se salvează…" : "Salvează"}</button></div>}
      </div>}
      {!compact && (part === "all" || part === "commissioning") && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-2"><h4 className="font-bold text-sm">Reglaje invertor</h4>
          <button className="text-[11px] font-bold text-left" style={{ color: "var(--blue)" }} onClick={() => setVal("reglaj", Object.fromEntries(REGLAJ.map(([k]) => [k, { val: TYPICAL[k][0], t: TYPICAL[k][1] }])))} data-testid="reglaj-typical">Completează valori orientative (verifică în invertor)</button></div>
        <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Valorile orientative nu confirmă reglarea efectivă a invertorului.</p>
        {REGLAJ.map(([k, l]) => (
          <div key={k} className="grid grid-cols-1 sm:grid-cols-[1fr_90px_80px] gap-2 mb-3 sm:mb-1.5 items-center text-xs">
            <span className="font-semibold sm:font-normal">{l}</span>
            <div className="grid grid-cols-2 sm:contents gap-2">
              <input className="den-input py-1" aria-label={`${l}: valoare`} placeholder="valoare" value={rg[k]?.val || ""} onChange={(e) => setR(k, "val", e.target.value)} data-testid={`reglaj-${k}-val`} />
              <input className="den-input py-1" aria-label={`${l}: timp`} placeholder="timp (s)" value={rg[k]?.t || ""} onChange={(e) => setR(k, "t", e.target.value)} data-testid={`reglaj-${k}-t`} />
            </div>
          </div>
        ))}
        <label className="mt-3 flex items-start gap-2 text-xs leading-5" style={{ color: "var(--ink)" }}>
          <input type="checkbox" className="mt-1 shrink-0" checked={rg.verified_by_installer === true} disabled={!reglajValuesComplete}
            onChange={(e) => setVal("reglaj", { ...rg, verified_by_installer: e.target.checked })}
            data-testid="reglaj-verified" />
          <span>Confirm că valorile au fost verificate efectiv pe invertor de instalator. Fără această confirmare, PDF-ul rămâne fișă de lucru.</span>
        </label>
      </div>}
      {!compact && (part === "all" || part === "commissioning") && <div className="rounded-xl border p-4 bg-white lg:col-span-2" style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2"><h4 className="font-bold text-sm">Teste și verificări PIF (Ord. ANRE 228/2018) — rezultate</h4>
          <button className="text-[11px] font-bold" style={{ color: "var(--blue)" }} onClick={() => setVal("tests", { ...ts, ...Object.fromEntries(TESTS.map((k) => [k, { ...(ts[k] || {}), ok: ts[k]?.ok || "DA" }])) })} data-testid="tests-all-da">Marchează DA pe rândurile necompletate (doar dacă e confirmat de certificatul de tip)</button></div>
        <div className="grid sm:grid-cols-3 gap-2">
          {TESTS.map((k) => (
            <div key={k} className="flex items-center gap-2 text-xs"><span className="w-28 shrink-0">{TLABEL[k[0]]} {Number(k.slice(1)) + 1}</span>
              <select className="den-input py-1 w-20" value={ts[k]?.ok || ""} onChange={(e) => setT(k, "ok", e.target.value)} data-testid={`test-${k}`}><option value="">—</option><option>DA</option><option>NU</option></select>
              <input className="den-input py-1" placeholder="observații / valori" value={ts[k]?.obs || ""} onChange={(e) => setT(k, "obs", e.target.value)} data-testid={`test-${k}-obs`} /></div>
          ))}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(160px,220px)_minmax(160px,220px)_1fr]">
          <label className="den-field"><span>Nr. proces-verbal teste</span>
            <input className="den-input" type="text" maxLength={100} value={form.pif_no || ""} onChange={(e) => setVal("pif_no", e.target.value)} data-testid="tests-pv-number" />
          </label>
          <label className="den-field"><span>Verdict operator</span>
            <select className="den-input" value={ts.verdict || ""} onChange={(e) => setVal("tests", { ...ts, verdict: e.target.value })} data-testid="tests-verdict">
              <option value="">— necompletat —</option><option value="Admis">Admis</option><option value="Respins">Respins</option>
            </select>
          </label>
          <label className="den-field"><span>Observații operator</span>
            <textarea className="den-input" rows={2} maxLength={1000} value={ts.od_observations || ""} onChange={(e) => setVal("tests", { ...ts, od_observations: e.target.value })} data-testid="tests-od-observations" />
          </label>
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Verdictul și observațiile se completează numai după comunicarea operatorului; nu sunt completate automat.</p>
      </div>}
    </div>
  );
}

