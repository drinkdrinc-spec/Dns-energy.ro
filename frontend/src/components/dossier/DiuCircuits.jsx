import { Plus, Trash2 } from "lucide-react";

const COLS = [["name", "Circuit", 150], ["curve", "Curbă", 50], ["breaker_a", "In (A)", 60], ["section", "Secț. (mm²)", 70], ["cable", "Tip cablu", 80],
  ["length", "L (m)", 55], ["rcd_ma", "DDR IΔn (mA)", 70], ["rcd_type", "DDR tip", 55]];
const MEAS = [["r_pe", "R PE (Ω)"], ["riso", "Riso (MΩ)"], ["rcd_i", "DDR I decl. (mA)"], ["rcd_t", "DDR t (ms)"]];
const PRAM = [["date", "Data măsurătorilor", "date"], ["instrument", "Aparat de măsură (tip, serie, certificat)"], ["verifier", "Verificator PRAM"],
  ["earth_ohm", "Rezistență dispersie măsurată (Ω)"], ["earth_limit", "Valoare admisă (Ω)"], ["soil", "Starea solului"], ["test_v", "Tensiune încercare izolație (V)"]];

export function DiuCircuits({ form, setVal }) {
  const cs = form.circuits || [];
  const pm = form.pram_m || {};
  const upd = (i, k, v) => setVal("circuits", cs.map((c, j) => (j === i ? { ...c, [k]: v } : c)));
  return (
    <div className="mt-4 space-y-4">
      <div>
        <div className="text-xs font-bold mb-2">Circuitele tabloului general (TG) și măsurătorile PRAM pe circuit — doar valori măsurate efectiv</div>
        <div className="overflow-x-auto">
          <table className="text-xs" data-testid="diu-circuits">
            <thead><tr>{[...COLS, ...MEAS].map(([k, l]) => <th key={k} className="px-1 py-1 text-left font-bold">{l}</th>)}<th /></tr></thead>
            <tbody>{cs.map((c, i) => (
              <tr key={i} data-testid={`diu-circuit-${i}`}>
                {COLS.map(([k, , w]) => <td key={k} className="px-1"><input className="den-input !py-1 !text-xs" style={{ width: w }} value={c[k] ?? ""} onChange={(e) => upd(i, k, e.target.value)} data-testid={`diu-c-${i}-${k}`} /></td>)}
                {MEAS.map(([k]) => <td key={k} className="px-1"><input className="den-input !py-1 !text-xs" style={{ width: 70, background: "#f7fbff" }} value={c[k] ?? ""} onChange={(e) => upd(i, k, e.target.value)} data-testid={`diu-c-${i}-${k}`} /></td>)}
                <td><button onClick={() => setVal("circuits", cs.filter((_, j) => j !== i))} data-testid={`diu-c-del-${i}`}><Trash2 size={13} style={{ color: "#b33333" }} /></button></td>
              </tr>))}</tbody>
          </table>
        </div>
        <button className="text-xs font-bold inline-flex items-center gap-1 mt-2" style={{ color: "var(--blue)" }} onClick={() => setVal("circuits", [...cs, { name: "", curve: "C" }])} data-testid="diu-c-add"><Plus size={13} /> Circuit</button>
      </div>
      <div className="grid sm:grid-cols-3 gap-2">
        {PRAM.map(([k, l, t]) => (
          <div key={k} className="den-field"><label>{l}</label>
            <input className="den-input" type={t || "text"} value={pm[k] ?? ""} onChange={(e) => setVal("pram_m", { ...pm, [k]: e.target.value })} data-testid={`diu-pram-${k}`} /></div>))}
      </div>
    </div>
  );
}
