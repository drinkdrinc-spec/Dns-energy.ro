import { F, Check, CatalogPick, INSTALL } from "./F";

export function GridCard({ grid, set, catalog, res }) {
  const s = (k) => (v) => set({ ...grid, [k]: v });
  const gr = res?.grid;
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-grid-card">
      <h4 className="font-bold text-sm mb-3">Branșament, măsură și tablou general</h4>
      <div className="grid sm:grid-cols-3 gap-3">
        <F label="Branșament cerut" value={grid.supply} onChange={s("supply")} options={["Trifazat", "Monofazat"]} testid="grid-supply" />
        <F label="Putere aprobată/cerută (kW)" type="number" value={grid.bransament_kw} onChange={s("bransament_kw")} testid="grid-bransament" />
        <F label={`Protecție BMP (A)${gr?.main_proposal ? ` · propus ${gr.main_proposal} A` : ""}`} type="number" value={grid.bmp_a} onChange={s("bmp_a")} testid="grid-bmp" />
        <F label="Cablu coloană BMP → TG" value={grid.column_cable} onChange={s("column_cable")} testid="grid-column" />
        <F label="Raport TC (dacă măsură prin TC)" value={grid.ct_ratio} onChange={s("ct_ratio")} testid="grid-ct" />
        <CatalogPick items={catalog} category="Smart meter" label="Smart meter (catalog)" onPick={(it) => set({ ...grid, meter: it.brand_model, meter_catalog_id: it.id })} testid="grid-meter-pick" />
        <F label="Smart meter" value={grid.meter} onChange={s("meter")} testid="grid-meter" />
        <F label="Întreruptor general TG" value={grid.tg_breaker} onChange={s("tg_breaker")} testid="grid-tg" />
        <F label="SPD AC" value={grid.spd_ac} onChange={s("spd_ac")} options={["tip 1+2", "tip 2", "tip 1"]} testid="grid-spd" />
        <F label="Diferențial general" value={grid.rcd} onChange={s("rcd")} testid="grid-rcd" />
        <F label="Rezistență priză pământ (Ω)" type="number" value={grid.grounding_ohm} onChange={s("grounding_ohm")} testid="grid-ground" />
        <F label="Temperatură minimă calcul (°C)" type="number" value={grid.tmin} onChange={s("tmin")} testid="grid-tmin" />
        <F label="Sistem legare la pământ" value={grid.earthing} onChange={s("earthing")} options={["TN-C-S", "TN-S", "TT"]} testid="grid-earthing" />
        <F label="Ik la punctul de racord (kA, din ATR/OD)" type="number" value={grid.ik_ka} onChange={s("ik_ka")} testid="grid-ik" />
        <F label="Întreruptor general TG (A)" type="number" value={grid.tg_breaker_a} onChange={s("tg_breaker_a")} testid="grid-tg-a" />
        <F label="Diferențial general IΔn (mA)" type="number" value={grid.rcd_ma} onChange={s("rcd_ma")} testid="grid-rcd-ma" />
        <F label="Coloană: secțiune (mm²)" type="number" value={grid.column_section} onChange={s("column_section")} testid="grid-col-section" />
        <F label="Coloană: lungime (m)" type="number" value={grid.column_length} onChange={s("column_length")} testid="grid-col-length" />
        <F label="Coloană: material" value={grid.column_material || "Cu"} onChange={s("column_material")} options={["Cu", "Al"]} testid="grid-col-mat" />
        <F label="Coloană: mod de pozare" value={grid.column_install || "D"} onChange={s("column_install")} options={INSTALL} testid="grid-col-install" />
        <F label="Smart meter: raport TC (gol = conectare directă)" value={grid.sm_ct_ratio} onChange={s("sm_ct_ratio")} testid="grid-sm-ct" />
        <F label="Conductor echipotențial rame PV (mm²)" type="number" value={grid.bond_section} onChange={s("bond_section")} testid="grid-bond" />
      </div>
      <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>Rezistența prizei de pământ se completează doar cu valoarea măsurată (buletin PRAM); aplicația nu estimează rezultate de măsurare.</p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Check label="Tablou antiinsularizare cerut prin ATR / soluția de racordare" value={grid.anti_required} onChange={s("anti_required")} testid="grid-anti" />
        {gr?.anti_auto && <span className="text-xs font-bold" style={{ color: "#b03a2e" }}>Peste 27 kW — tabloul se adaugă automat</span>}
      </div>
      {(grid.anti_required || gr?.anti) && (
        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <F label="Releu protecție interfață" value={grid.anti_relay} onChange={s("anti_relay")} testid="grid-anti-relay" />
          <F label="Element de decuplare" value={grid.anti_breaker} onChange={s("anti_breaker")} testid="grid-anti-breaker" />
        </div>
      )}
    </div>
  );
}
