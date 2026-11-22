import { F, Check, CatalogPick, INSTALL } from "./F";
import { Plus, Trash2, Wand2 } from "lucide-react";

const DEFAULT_TEG_CIRCUITS = [
  { name: "Iluminat", breaker: "C10", poles: "1P+N", rcd: "30mA" },
  { name: "Prize 1", breaker: "C16", poles: "1P+N", rcd: "30mA" },
  { name: "Prize 2", breaker: "C16", poles: "1P+N", rcd: "30mA" },
  { name: "Forță", breaker: "C20", poles: "3P+N", rcd: "30mA" },
];

export function GridCard({ grid, set, catalog, res, onSave, saving = false }) {
  const s = (k) => (v) => set({ ...grid, [k]: v });
  const gr = res?.grid;
  const autoInverterCables = (res?.inverters || []).map((item, index) => {
    const section = item.proposals?.ac?.section;
    if (!section) return null;
    return `INV ${index + 1}: ${item.tri ? "5" : "3"}×${section} mm²`;
  }).filter(Boolean).join(" · ");
  const circuits = Array.isArray(grid.circuits) ? grid.circuits : DEFAULT_TEG_CIRCUITS;
  const meterSeparate = (grid.smart_meter_mode || (grid.meter_enabled ? "Contor separat" : "Inclus în invertor")) === "Contor separat";
  const setCircuit = (index, patch) => set({ ...grid, circuits: circuits.map((row, i) => i === index ? { ...row, ...patch } : row) });
  return (
    <>
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-grid-card">
      <h4 className="font-bold text-sm mb-3">Branșament & măsură</h4>
      <div className="grid sm:grid-cols-3 gap-3">
        <F label="Branșament" value={grid.supply} onChange={s("supply")} options={["Trifazat", "Monofazat"]} testid="grid-supply" />
        <F label="Putere aprobată / cerută (kW)" type="number" value={grid.bransament_kw} onChange={s("bransament_kw")} testid="grid-bransament" />
        <F label={`Protecție BMP existentă (A)${gr?.main_proposal ? ` · tipic ${gr.main_proposal} A` : ""}`} type="number" value={grid.bmp_a} onChange={s("bmp_a")} testid="grid-bmp" />
        <F label="Protecție generală după BMP (A)" type="number" value={grid.tg_breaker_a} onChange={s("tg_breaker_a")} testid="grid-tg-a" />
        <F label="Măsură" value={grid.measure_mode || "Directă"} onChange={s("measure_mode")} options={["Directă", "Prin TC (transformatoare de curent)"]} testid="grid-measure-mode" />
        <F label="Smart meter" value={grid.smart_meter_mode || (grid.meter_enabled ? "Contor separat" : "Inclus în invertor")} onChange={(value) => set({ ...grid, smart_meter_mode: value, meter_enabled: value === "Contor separat" })} options={["Contor separat", "Inclus în invertor"]} testid="grid-smart-meter-mode" />
      </div>
      {meterSeparate && <div className="mt-4 rounded-lg border p-3" style={{ borderColor: "var(--line)" }}>
        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <CatalogPick items={catalog} category="Smart meter" label="Alege modelul din catalog" onPick={(it) => set({ ...grid, meter_enabled: true, meter: it.brand_model, meter_catalog_id: it.id })} testid="grid-meter-pick" />
          <F label="Model smart meter" value={grid.meter} onChange={(value) => set({ ...grid, meter_enabled: true, meter: value })} testid="grid-meter" />
          <F label="Serie contor" value={grid.meter_serial} onChange={(value) => set({ ...grid, meter_enabled: true, meter_serial: value })} testid="grid-meter-serial" />
          <F label="Date tehnice contor (tip, tensiune, curent)" value={grid.meter_specs} onChange={(value) => set({ ...grid, meter_enabled: true, meter_specs: value })} testid="grid-meter-specs" />
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Modelul contorului apare sub simbolul lui în schema monofilară. Contorul OD rămâne comun, la punctul de racord.</p>
      </div>}
      </div>
      <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-topology-card">
        <h4 className="font-bold text-sm mb-3">Topologie, protecții & TEG</h4>
        <div className="grid sm:grid-cols-2 gap-3">
          <F label="Alimentare TEG" value={grid.teg_supply || "Auto (derivat)"} onChange={s("teg_supply")} options={["Auto (derivat)", "Rețea (fără back-up)", "Load (2× BMP)", "Huawei Back-up Box"]} testid="grid-teg-supply" />
          <F label="Backup" value={grid.backup_mode || "—"} onChange={s("backup_mode")} options={["—", "Total (tot TEG-ul pe backup)", "Parțial (doar circuite critice)"]} testid="grid-backup-mode" />
          <F label="SPD DC" value={grid.spd_dc || "SPD 2P · 600 V"} onChange={s("spd_dc")} options={["SPD 2P · 600 V", "SPD 2P · 1000 V", "SPD 2P · 1500 V", "SPD integrat în invertor"]} testid="grid-spd-dc" />
          <F label="SPD AC" value={grid.spd_ac || ""} onChange={s("spd_ac")} options={["SPD 2P · Tip 2 · Up 1,5 kV", "SPD 4P · Tip 2 · Up 1,5 kV", "SPD 2P · Tip 1+2", "SPD 4P · Tip 1+2"]} testid="grid-spd" />
          <F label="Conductor solar" value={grid.solar_conductor || "H1Z2Z2-K 6 mm²"} onChange={s("solar_conductor")} testid="grid-solar-conductor" />
          <F label="Cabluri AC propuse pe invertor" value={grid.inverter_ac_cable || autoInverterCables} onChange={s("inverter_ac_cable")} testid="grid-inverter-ac-cable" />
          <F label="Siguranță generală TEG" value={grid.teg_main_protection || ""} onChange={s("teg_main_protection")} testid="grid-teg-main-protection" />
          <F label="Priză de pământ" value={grid.grounding_status || "—"} onChange={s("grounding_status")} options={["—", "Nouă", "Existentă"]} testid="grid-ground-status" />
        </div>
        <div className="mt-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <b className="text-xs">Circuite TEG</b>
            <div className="flex items-center gap-2"><span className="rounded-lg border px-3 py-1 text-xs" style={{ borderColor: "var(--line)" }}>{circuits.length}</span>
              <button type="button" className="inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => set({ ...grid, circuits: DEFAULT_TEG_CIRCUITS.map((row) => ({ ...row })) })}><Wand2 size={13} /> Propune circuitele</button></div>
          </div>
          <div className="space-y-2">
            {circuits.map((circuit, index) => <div key={index} className="grid grid-cols-2 sm:grid-cols-[minmax(72px,1fr)_minmax(62px,.8fr)_minmax(68px,.8fr)_minmax(80px,.9fr)_32px] gap-2 rounded-lg border p-2 items-end" style={{ borderColor: "var(--line)" }} data-testid={`teg-circuit-${index}`}>
              <F label="Circuit" value={circuit.name} onChange={(value) => setCircuit(index, { name: value })} testid={`teg-circuit-${index}-name`} />
              <F label="Siguranță" value={circuit.breaker || "C16"} onChange={(value) => setCircuit(index, { breaker: value })} options={["C6", "C10", "C13", "C16", "C20", "C25", "C32", "C40"]} testid={`teg-circuit-${index}-breaker`} />
              <F label="Poli" value={circuit.poles || "1P+N"} onChange={(value) => setCircuit(index, { poles: value })} options={["1P+N", "3P+N"]} testid={`teg-circuit-${index}-poles`} />
              <F label="Diferențial" value={circuit.rcd || "fără dif."} onChange={(value) => setCircuit(index, { rcd: value })} options={["fără dif.", "30mA", "300mA"]} testid={`teg-circuit-${index}-rcd`} />
              <button type="button" className="mb-1.5 rounded p-1.5" aria-label={`Șterge circuitul ${index + 1}`} onClick={() => set({ ...grid, circuits: circuits.filter((_, i) => i !== index) })} data-testid={`teg-circuit-${index}-remove`}><Trash2 size={15} style={{ color: "#8d8d8d" }} /></button>
            </div>)}
          </div>
          <button type="button" className="mt-2 inline-flex items-center gap-1 text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => set({ ...grid, circuits: [...circuits, { name: `Circuit ${circuits.length + 1}`, breaker: "C16", poles: "1P+N", rcd: "fără dif." }] })} data-testid="teg-circuit-add"><Plus size={14} /> Adaugă circuit</button>
          <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Valorile propuse trebuie confirmate cu proiectul și fișele echipamentelor.</p>
        </div>
      <details className="mt-4 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer text-xs font-semibold">Detalii tehnice · cabluri, protecții și măsurători</summary>
        <div className="grid sm:grid-cols-3 gap-3 mt-3">
          <F label="Cablu coloană BMP → TG" value={grid.column_cable || gr?.main_column_cable_proposal} onChange={s("column_cable")} testid="grid-column" />
          <F label="Raport TC (dacă măsură prin TC)" value={grid.ct_ratio} onChange={s("ct_ratio")} testid="grid-ct" />
          <F label="Întreruptor general TG" value={grid.tg_breaker} onChange={s("tg_breaker")} testid="grid-tg" />
          <F label="SPD AC" value={grid.spd_ac} onChange={s("spd_ac")} options={["tip 1+2", "tip 2", "tip 1"]} testid="grid-spd" />
          <F label="Diferențial general" value={grid.rcd} onChange={s("rcd")} testid="grid-rcd" />
          <F label="Rezistență priză pământ — măsurată (Ω)" type="number" value={grid.grounding_ohm} onChange={s("grounding_ohm")} testid="grid-ground" />
          <F label="Valoare admisă priză (Ω) — stabilită de proiectant" type="number" value={grid.grounding_limit} onChange={s("grounding_limit")} testid="grid-ground-limit" />
          <F label="Temperatură minimă calcul (°C)" type="number" value={grid.tmin} onChange={s("tmin")} testid="grid-tmin" />
          <F label="Sistem legare la pământ" value={grid.earthing} onChange={s("earthing")} options={["TN-C-S", "TN-S", "TT"]} testid="grid-earthing" />
          <F label="Ik la punctul de racord (kA, din ATR/OD)" type="number" value={grid.ik_ka} onChange={s("ik_ka")} testid="grid-ik" />
          <F label="Diferențial general IΔn (mA)" type="number" value={grid.rcd_ma} onChange={s("rcd_ma")} testid="grid-rcd-ma" />
          <F label="Coloană: secțiune (mm²)" type="number" value={grid.column_section} onChange={s("column_section")} testid="grid-col-section" />
          <F label="Coloană: lungime (m)" type="number" value={grid.column_length} onChange={s("column_length")} testid="grid-col-length" />
          <F label="Coloană: material" value={grid.column_material || "Cu"} onChange={s("column_material")} options={["Cu", "Al"]} testid="grid-col-mat" />
          <F label="Coloană: mod de pozare" value={grid.column_install || "D"} onChange={s("column_install")} options={INSTALL} testid="grid-col-install" />
          <F label="Smart meter: raport TC (gol = conectare directă)" value={grid.sm_ct_ratio} onChange={s("sm_ct_ratio")} testid="grid-sm-ct" />
          <F label="Conductor echipotențial rame PV (mm²)" type="number" value={grid.bond_section} onChange={s("bond_section")} testid="grid-bond" />
        </div>
      </details>
      <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>Rezistența prizei de pământ se completează doar cu valoarea măsurată (buletin PRAM); aplicația nu estimează rezultate de măsurare.</p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Check label="Tablou antiinsularizare cerut prin ATR / soluția de racordare" value={grid.anti_required} onChange={s("anti_required")} testid="grid-anti" />
        {gr?.anti_backup ? <span className="text-xs font-bold" style={{ color: "#b03a2e" }}>Backup selectat — include protecția antiinsularizare cu bobină de declanșare; verifică soluția din ATR</span>
          : gr?.anti_auto && <span className="text-xs font-bold" style={{ color: "#b03a2e" }}>Peste 27 kW sau curent calculat peste 63 A — propunere automată</span>}
      </div>
      {(grid.anti_required || gr?.anti) && (
        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <F label="Releu protecție interfață" value={grid.anti_relay} onChange={s("anti_relay")} testid="grid-anti-relay" />
          <F label="Element de decuplare" value={grid.anti_breaker} onChange={s("anti_breaker")} testid="grid-anti-breaker" />
        </div>
      )}
      {onSave && <div className="mt-4 flex justify-end"><button type="button" className="rounded-lg px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60" style={{ background: "var(--green)" }} onClick={onSave} disabled={saving} data-testid="save-cef-card">{saving ? "Se salvează…" : "Salvează"}</button></div>}
      </div>
    </>
  );
}
