import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const REGLAJ = [["u1", "Tensiune maximală treapta I"], ["u2", "Tensiune minimală treapta II"], ["f1", "Frecvență treapta I"], ["f2", "Frecvență treapta II"],
  ["u10", "Tensiune maximă (medie 10 min)"], ["rec", "Pornire / repornire după întrerupere RED"], ["hvrt", "HVRT"], ["lvrt", "LVRT"], ["droop", "Statism la variația frecvenței"]];
const TYPICAL = { u1: ["1,15 Un", "0,5"], u2: ["0,85 Un", "3,2"], f1: ["52 Hz", "0,5"], f2: ["47,5 Hz", "0,5"], u10: ["253 V", "603"], rec: ["—", "900"], hvrt: ["264,5 V", "Activată"], lvrt: ["184,5 V", "Activată"], droop: ["5 %", "—"] };
const TESTS = [...Array(10).keys()].map((i) => `a${i}`).concat([...Array(4).keys()].map((i) => `f${i}`), [...Array(7).keys()].map((i) => `c${i}`));
const TLABEL = { a: "Test categoria A", f: "Domeniu de frecvență", c: "Verificare" };

export function DossierExtras({ form, setVal, compact = false }) {
  const pramInput = useRef(null);
  const [pramBusy, setPramBusy] = useState(false);
  const rg = form.reglaj || {}, ts = form.tests || {};
  const setR = (k, f, v) => setVal("reglaj", { ...rg, [k]: { ...(rg[k] || {}), [f]: v }, verified_by_installer: false });
  const reglajValuesComplete = REGLAJ.every(([k]) => String(rg[k]?.val || "").trim() && String(rg[k]?.t || "").trim());
  const setT = (k, f, v) => setVal("tests", { ...ts, [k]: { ...(ts[k] || {}), [f]: v } });
  return (
    <div id={compact ? "diu-executant" : undefined} className="mt-6 grid lg:grid-cols-2 gap-4" data-testid="dossier-extras">
      {compact && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <h4 className="font-bold text-sm mb-1">Semnătura reprezentantului firmei</h4>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Documentele au un singur semnatar: reprezentantul firmei executante. Semnătura și ștampila se preiau din setările firmei, dacă sunt configurate; aplicația nu inventează semnături.</p>
      </div>}
      {!compact && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
        <h4 className="font-bold text-sm mb-2">Buletin PRAM</h4>
        <label className="den-field block mb-2"><span className="text-xs">Sursa buletinului</span>
          <select className="den-input" value={form.pram_source || "internal"} onChange={(e) => setVal("pram_source", e.target.value)} data-testid="pram-source">
            <option value="internal">Îl întocmim noi — numai cu măsurători reale</option>
            <option value="third_party">Încarc buletin valabil de la firmă terță</option>
          </select>
        </label>
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
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Nu se generează și nu se completează automat nicio valoare măsurată. Un buletin terț se folosește ca PDF-ul încărcat.</p>
      </div>}
      {!compact && <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }}>
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
      {!compact && <div className="rounded-xl border p-4 bg-white lg:col-span-2" style={{ borderColor: "var(--line)" }}>
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

