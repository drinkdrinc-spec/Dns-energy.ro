import { useMemo, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { Ruler, Sun, Layers3, House, Copy, Check } from "lucide-react";
import { toast } from "sonner";

const STOCK_LENGTHS = [2, 2.5, 3, 3.5, 3.6, 4, 4.75, 6];
const ceil = (n) => Math.ceil(Math.max(0, Number(n) || 0));
const fmt = (n, digits = 2) => new Intl.NumberFormat("ro-RO", { maximumFractionDigits: digits }).format(n);

function Field({ label, value, onChange, min, max, step = 1, suffix = "", options }) {
  return <label className="block text-sm font-semibold text-slate-700">
    {label}
    {options ? <select className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal" value={value} onChange={(e) => onChange(e.target.value)}>{options.map((o) => { const optionValue = typeof o === "object" ? o.value : o; const optionLabel = typeof o === "object" ? o.label : o; return <option key={optionValue} value={optionValue}>{optionLabel}{suffix}</option>; })}</select>
      : <div className="mt-1.5 flex items-center rounded-lg border border-slate-300 bg-white px-3"><input className="w-full min-w-0 border-0 bg-transparent py-2.5 font-normal outline-none" type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(e.target.value)} /><span className="text-slate-500">{suffix}</span></div>}
  </label>;
}

function Metric({ label, value, detail }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</div><div className="mt-1 text-2xl font-extrabold text-slate-900">{value}</div>{detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}</div>;
}

export default function StructureCalculator() {
  const [type, setType] = useState("tile");
  const [panels, setPanels] = useState("12");
  const [panelWidth, setPanelWidth] = useState("1134");
  const [panelLength, setPanelLength] = useState("1762");
  const [orientation, setOrientation] = useState("portrait");
  const [perRow, setPerRow] = useState("4");
  const [hookSpacing, setHookSpacing] = useState("0.85");
  const [barLength, setBarLength] = useState("4.75");
  const [tableSize, setTableSize] = useState("12");
  const [tableRows, setTableRows] = useState("2");

  const result = useMemo(() => {
    const count = Math.max(type === "ground" ? 4 : 1, Math.min(1000, Number(panels) || 1));
    const cols = Math.max(1, Math.min(count, Number(perRow) || 1));
    const rows = ceil(count / cols);
    const moduleAcross = (orientation === "portrait" ? Number(panelWidth) : Number(panelLength)) / 1000;
    const rowPanels = Array.from({ length: rows }, (_, row) => Math.min(cols, count - row * cols));
    const railRuns = rowPanels.map((inRow) => inRow * moduleAcross + Math.max(0, inRow - 1) * 0.02);
    const railCount = rows * 2;
    const railMeters = railRuns.reduce((sum, run) => sum + run * 2, 0);
    const hooks = railRuns.reduce((sum, run) => sum + 2 * (ceil(run / (Number(hookSpacing) || 0.85)) + 1), 0);
    const ends = rows * 4;
    const middles = rowPanels.reduce((sum, inRow) => sum + Math.max(0, inRow - 1) * 2, 0);
    const chosenBar = Number(barLength) || 2;
    const bars = railRuns.reduce((sum, run) => sum + 2 * ceil(run / chosenBar), 0);

    const tableCap = Math.max(4, Math.min(40, Number(tableSize) || 4));
    const rowCount = Math.max(1, Math.min(tableCap, Number(tableRows) || 1));
    const tableTotal = ceil(count / tableCap);
    let groundEnds = 0;
    let groundMiddles = 0;
    for (let t = 0; t < tableTotal; t++) {
      let left = Math.min(tableCap, count - t * tableCap);
      const q = Math.floor(left / rowCount), extra = left % rowCount;
      for (let r = 0; r < rowCount; r++) {
        const n = q + (r < extra ? 1 : 0);
        if (n > 0) { groundEnds += 4; groundMiddles += 2 * Math.max(0, n - 1); }
      }
    }
    return { count, cols, rows, railRun, railCount, railMeters, hooks, ends, middles, bars, chosenBar, tableTotal, groundEnds, groundMiddles, groundRows: rowCount };
  }, [type, panels, panelWidth, panelLength, orientation, perRow, hookSpacing, barLength, tableSize, tableRows]);

  const title = type === "ground" ? "Structură la sol" : type === "sheet" ? "Acoperiș din tablă · Minirail" : "Acoperiș cu țiglă";
  const copySummary = async () => {
    const text = type === "ground"
      ? `${title}\nPanouri: ${result.count}\nPanouri/masă: ${tableSize} · Mese: ${result.tableTotal}\nCleme de capăt: ${result.groundEnds} · Cleme de mijloc: ${result.groundMiddles}`
      : `${title}\nPanouri: ${result.count} (${result.cols}/rând × ${result.rows} rânduri)\n${type === "tile" ? `Picioare de țiglă: ${result.hooks}\n` : `Minirailuri: ${result.count * 4}\n`}Bare ${result.chosenBar} m: ${result.bars} buc. · necesar liniar: ${fmt(result.railMeters)} m\nCleme de capăt: ${result.ends} · Cleme de mijloc: ${result.middles}`;
    try { await navigator.clipboard.writeText(text); toast.success("Calculul a fost copiat."); } catch { toast.error("Nu am putut copia calculul."); }
  };

  return <div>
    <PageHeader eyebrow="Proiectare montaj" title="Calculator structură" sub="Estimare rapidă pentru acoperiș cu țiglă, tablă și mese la sol." />
    <div className="mb-5 grid grid-cols-1 gap-2 sm:grid-cols-3" role="tablist" aria-label="Tip structură">
      {[["tile", House, "Acoperiș cu țiglă"], ["sheet", Layers3, "Acoperiș din tablă"], ["ground", Sun, "Structură la sol"]].map(([key, Icon, label]) => <button key={key} role="tab" aria-selected={type === key} onClick={() => setType(key)} className={`flex min-h-12 items-center justify-center gap-2 rounded-xl border px-3 py-3 text-sm font-bold ${type === key ? "border-blue-700 bg-blue-50 text-blue-800" : "border-slate-200 bg-white text-slate-600"}`}><Icon size={18} />{label}</button>)}
    </div>

    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.9fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-extrabold text-slate-900"><Ruler size={20} />Datele montajului</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Număr total de panouri" value={panels} onChange={setPanels} min={type === "ground" ? "4" : "1"} max="1000" />
          <Field label="Orientare panou" value={orientation} onChange={setOrientation} options={[{ value: "portrait", label: "Portret" }, { value: "landscape", label: "Peisaj" }]} />
          <Field label="Lățime panou" value={panelWidth} onChange={setPanelWidth} min="1" suffix="mm" />
          <Field label="Lungime panou" value={panelLength} onChange={setPanelLength} min="1" suffix="mm" />
          {type !== "ground" && <>
            <Field label="Panouri pe un rând" value={perRow} onChange={setPerRow} min="1" max={panels || 1} />
            {type === "tile" && <>
              <Field label="Lungime bară de prindere" value={barLength} onChange={setBarLength} options={STOCK_LENGTHS.map(String)} suffix=" m" />
              <Field label="Distanță maximă între picioare" value={hookSpacing} onChange={setHookSpacing} options={["0.8", "0.85", "0.9"]} suffix=" m" />
            </>}
          </>}
          {type === "ground" && <>
            <Field label="Panouri pe masă" value={tableSize} onChange={setTableSize} options={Array.from({ length: 37 }, (_, i) => String(i + 4))} />
            <Field label="Rânduri de panouri pe masă" value={tableRows} onChange={setTableRows} min="1" max={tableSize || 40} />
          </>}
        </div>
        <p className="mt-4 text-xs leading-5 text-slate-500">Cantitățile sunt estimative, calculate din dimensiunile și așezarea introduse. Verifică schema sistemului de prindere și cerințele producătorului pentru acoperiș, vânt și zăpadă.</p>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3"><div><div className="text-xs font-bold uppercase tracking-wide text-slate-500">Rezultatul estimării</div><h2 className="text-lg font-extrabold text-slate-900">{title}</h2></div><button onClick={copySummary} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-slate-700"><Copy size={16} />Copiază</button></div>
        {type === "ground" ? <div className="grid grid-cols-2 gap-3">
          <Metric label="Mese necesare" value={result.tableTotal} detail={`${tableSize} panouri/masă (maxim)`} />
          <Metric label="Panouri totale" value={result.count} />
          <Metric label="Cleme de capăt" value={`${result.groundEnds} buc.`} detail={`${result.groundRows} rânduri / masă`} />
          <Metric label="Cleme de mijloc" value={`${result.groundMiddles} buc.`} detail="calculate între panourile din fiecare rând" />
        </div> : <div className="grid grid-cols-2 gap-3">
          <Metric label="Panouri" value={result.count} detail={`${result.cols} pe rând × ${result.rows} rânduri`} />
          {type === "tile" ? <Metric label="Picioare de țiglă" value={`${result.hooks} buc.`} detail="max. 90 cm între punctele de prindere" /> : <Metric label="Minirailuri" value={`${result.count * 4} buc.`} detail="estimare inițială: 4/panou" />}
          <Metric label="Cleme de capăt" value={`${result.ends} buc.`} detail="2 șine / rând" />
          <Metric label="Cleme de mijloc" value={`${result.middles} buc.`} detail="2 pentru fiecare îmbinare dintre panouri" />
          {type === "tile" && <Metric label={`Bare de ${result.chosenBar} m`} value={`${result.bars} buc.`} detail={`${fmt(result.railMeters)} m liniari de șină`} />}
        </div>}
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950"><div className="flex items-center gap-2 font-bold"><Check size={16} />Cantitățile se actualizează automat</div><div className="mt-1 text-xs leading-5">{type === "sheet" ? "Pentru Minirail, estimarea folosește 4 bucăți pentru fiecare panou; adaptează la sistemul și instrucțiunile producătorului." : type === "ground" ? "Numărul de cleme ține cont de panourile pe rând și de mesele complete sau parțiale." : "Picioarele sunt distribuite la maximum 90 cm de-a lungul fiecărei șine. Lungimile disponibile: 2, 2,5, 3, 3,5, 3,6, 4, 4,75 și 6 m."}</div></div>
      </section>
    </div>
  </div>;
}

