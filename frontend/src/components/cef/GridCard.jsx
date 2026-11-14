import { F, Check, CatalogPick, INSTALL } from "./F";

export function GridCard({ grid, set, catalog, res, inverters = [], groundingOhm, groundingLimit, showIntro = true }) {
  const s = (k) => (v) => set({ ...grid, [k]: v });
  const gr = res?.grid;
  const circuits = grid.circuits?.length ? grid.circuits : Array.from({ length: 4 }, (_, i) => ({ name: `Circuit ${i + 1}` }));
  const setCircuits = (next) => set({ ...grid, circuits: next });
  const backupInverters = inverters.filter((inv) => inv.backup?.enabled);
  const derivedSupply = backupInverters.length ? "Load (2× BMP)" : "Rețea (fără back-up)";
  const derivedBackup = backupInverters.some((inv) => inv.backup?.type === "total") ? "Total" : backupInverters.length ? "Parțial" : "—";
  const measuredGround = groundingOhm || grid.grounding_ohm || "";
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="cef-grid-card">
      {showIntro && <><h4 className="font-bold text-sm mb-1">Tablouri electrice și circuite</h4>
      <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Tablourile se propun din branșament și echipamente. Verifică detaliile electrice când ai ATR-ul sau proiectul.</p></>}
      <div className="mb-3 grid gap-3 sm:grid-cols-3" data-testid="sld-board-selection">
        <F label="Tablou CEF — model / descriere" value={grid.pv_board_model} onChange={s("pv_board_model")} placeholder="ex. tablou PV DC/AC" testid="grid-pv-board-model" />
        <F label="Tablou general TG — model / descriere" value={grid.tg_board_model} onChange={s("tg_board_model")} placeholder="ex. tablou general 3F" testid="grid-tg-board-model" />
        <F label="Tablou protecții — module DIN" type="number" value={grid.protection_modules ?? 10} onChange={s("protection_modules")} testid="grid-protection-modules" />
      </div>
      <details className="mb-4 rounded-xl border bg-white px-3 py-3" style={{ borderColor: "var(--line)" }} data-testid="grid-advanced-details">
        <summary className="cursor-pointer text-sm font-bold">Protecții și dimensionare automată <span className="ml-1 text-xs font-normal" style={{ color: "var(--muted)" }}>· opțional</span></summary>
        <div className="mt-3">
      <div className="mb-4 rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="teg-topology-values">
        <div className="grid sm:grid-cols-2 gap-3">
          <div><F label="Alimentare TEG" value={grid.teg_supply || "Auto (derivat)"} onChange={s("teg_supply")} options={["Auto (derivat)", "Rețea (fără back-up)", "Load (2× BMP)"]} testid="grid-teg-supply" />
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Derivat din CEF: {derivedSupply}</p></div>
          <div><F label="Backup" value={grid.backup_mode || "—"} onChange={s("backup_mode")} options={["—", "Parțial", "Total"]} testid="grid-backup-mode" />
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Derivat din CEF: {derivedBackup}; backup parțial = doar circuitele bifate ca backup.</p></div>
          <div><F label="SPD CC" value={grid.spd_dc} onChange={s("spd_dc")} placeholder="SPD 2P · 600 V" testid="grid-spd-dc" />{!grid.spd_dc && <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Propunere orientativă: SPD 2P · 600 V</p>}</div>
          <div><F label="SPD AC" value={grid.spd_ac} onChange={s("spd_ac")} placeholder="SPD 2P/4P · Tip 2 · Up 1,5 kV" testid="grid-spd-ac" />{!grid.spd_ac && <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Propunere orientativă în funcție de numărul de faze.</p>}</div>
          <div><F label="Conductor solar" value={grid.solar_cable} onChange={s("solar_cable")} placeholder="H1Z2Z2-K 6 mm²" testid="grid-solar-cable" />{!grid.solar_cable && <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Propunere orientativă: H1Z2Z2-K 6 mm²</p>}</div>
          <div><F label="Cablu AC invertor → BMP/TEG" value={grid.inv_to_bmp_cable} onChange={s("inv_to_bmp_cable")} placeholder="ex. RVK 3×6 mm² Cu" testid="grid-inv-teg-cable" /></div>
          <F label="Protecție generală TEG (A)" type="number" value={grid.tg_breaker_a} onChange={s("tg_breaker_a")} testid="grid-tg-a" />
          <F label="Siguranță generală TEG / diferențial" value={grid.tg_general} onChange={s("tg_general")} placeholder="32 A 2P dif. 30 mA" testid="grid-tg-general" />
          <F label="Priză de pământ" value={grid.earth_socket || "—"} onChange={s("earth_socket")} options={["—", "Nouă", "Existentă"]} testid="grid-earth-socket" />
          <div><F label="RD (Ω) — din buletinul PRAM" type="number" value={measuredGround} onChange={s("grounding_ohm")} testid="grid-ground" />
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>Valoare măsurată: {measuredGround ? `${measuredGround} Ω` : "necompletată"}; limită: {groundingLimit || grid.grounding_limit || "≤ 4 Ω implicit"}.</p></div>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--green)" }}>Valorile calculabile pentru branșament și echipamente se completează automat, păstrând orice modificare manuală.</p>
      </div>
      <div className="grid sm:grid-cols-3 gap-3">
        <F label="Branșament cerut" value={grid.supply} onChange={s("supply")} options={["Trifazat", "Monofazat"]} testid="grid-supply" />
        <F label="Putere aprobată/cerută (kW)" type="number" value={grid.bransament_kw} onChange={s("bransament_kw")} testid="grid-bransament" />
        <F label={`Protecție BMP (A)${gr?.main_proposal ? ` · propus ${gr.main_proposal} A` : ""}`} type="number" value={grid.bmp_a} onChange={s("bmp_a")} testid="grid-bmp" />
        <F label="Cablu coloană BMP → TG" value={grid.column_cable} onChange={s("column_cable")} testid="grid-column" />
        <F label="Raport TC (dacă măsură prin TC)" value={grid.ct_ratio} onChange={s("ct_ratio")} testid="grid-ct" />
        <CatalogPick items={catalog} category="Smart meter" selectedId={grid.meter_catalog_id} label="Smart meter (catalog)" onPick={(it) => set({ ...grid, meter: it.brand_model, meter_catalog_id: it.id })} testid="grid-meter-pick" />
        <F label="Smart meter" value={grid.meter} onChange={s("meter")} testid="grid-meter" />
        <F label="Întreruptor general TG" value={grid.tg_breaker} onChange={s("tg_breaker")} testid="grid-tg" />
        <F label="Diferențial general" value={grid.rcd} onChange={s("rcd")} testid="grid-rcd" />
        <F label="Valoare admisă priză (Ω) — stabilită de proiectant" type="number" value={grid.grounding_limit} onChange={s("grounding_limit")} testid="grid-ground-limit" />
        <F label="Temperatură minimă calcul (°C)" type="number" value={grid.tmin} onChange={s("tmin")} testid="grid-tmin" />
        <F label="Sistem legare la pământ" value={grid.earthing} onChange={s("earthing")} options={["TN-C-S", "TN-S", "TT"]} testid="grid-earthing" />
        <F label="Ik la punctul de racord (kA, din ATR/OD)" type="number" value={grid.ik_ka} onChange={s("ik_ka")} testid="grid-ik" />
        <F label="Diferențial general IΔn (mA)" type="number" value={grid.rcd_ma ?? 30} onChange={s("rcd_ma")} testid="grid-rcd-ma" />
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
        </div>
      </details>
      <div className="mt-4 rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="teg-circuits">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h5 className="text-sm font-bold">Circuite TEG <span className="font-normal" style={{ color: "var(--muted)" }}>({circuits.length})</span></h5>
            <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Apar ca ramuri distincte în schemă. Completează protecțiile și secțiunile conform proiectului.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }}
              onClick={() => setCircuits([
                { name: "Iluminat", breaker_a: 10, curve: "C", poles: "1P+N", rcd_ma: 30 },
                { name: "Prize 1", breaker_a: 16, curve: "C", poles: "1P+N", rcd_ma: 30 },
                { name: "Prize 2", breaker_a: 16, curve: "C", poles: "1P+N", rcd_ma: 30 },
                { name: "Forță", breaker_a: 20, curve: "C", poles: "3P+N", rcd_ma: 30 },
              ])} data-testid="propose-teg-circuits">✣ Propune circuitele</button>
            <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }}
              onClick={() => setCircuits([...circuits, { name: `Circuit ${circuits.length + 1}` }])} data-testid="add-teg-circuit">＋ Adaugă circuit</button>
          </div>
        </div>
        <div className="mt-3 space-y-2">
          {circuits.map((circuit, i) => <div key={i} className="grid sm:grid-cols-[minmax(0,1fr)_100px_90px_100px_90px_auto] gap-2 items-end rounded-lg border p-2" style={{ borderColor: "var(--line)" }}>
            <F label={`Circuit ${i + 1}`} value={circuit.name || ""} onChange={(v) => setCircuits(circuits.map((x, j) => j === i ? { ...x, name: v } : x))} testid={`teg-circuit-${i}-name`} />
            <F label="Protecție" value={circuit.breaker_a ? `${circuit.curve || "C"}${circuit.breaker_a}` : ""} options={["B6", "B10", "B16", "B20", "C10", "C16", "C20", "C25", "C32"]} onChange={(v) => setCircuits(circuits.map((x, j) => j === i ? { ...x, curve: v.slice(0, 1), breaker_a: Number(v.slice(1)) } : x))} testid={`teg-circuit-${i}-breaker`} />
            <F label="Poli" value={circuit.poles || ""} options={["1P+N", "2P", "3P", "3P+N", "4P"]} onChange={(v) => setCircuits(circuits.map((x, j) => j === i ? { ...x, poles: v } : x))} testid={`teg-circuit-${i}-poles`} />
            <F label="Cablu (mm²)" type="number" value={circuit.cable_section} onChange={(v) => setCircuits(circuits.map((x, j) => j === i ? { ...x, cable_section: v } : x))} testid={`teg-circuit-${i}-cable`} />
            <F label="DDR (mA)" value={circuit.rcd_ma ? String(circuit.rcd_ma) : ""} options={["30", "100", "300"]} onChange={(v) => setCircuits(circuits.map((x, j) => j === i ? { ...x, rcd_ma: Number(v) } : x))} testid={`teg-circuit-${i}-rcd`} />
            <button type="button" aria-label={`Șterge circuitul ${i + 1}`} disabled={circuits.length === 1} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40" style={{ borderColor: "var(--line)" }} onClick={() => setCircuits(circuits.filter((_, j) => j !== i))}>Șterge</button>
          </div>)}
        </div>
        <p className="text-[11px] mt-3" style={{ color: "var(--muted)" }}>Schema include automat DDR general de 30 mA (propunere), tabloul de protecții și bara PE. Confirmă valorile nominale și circuitele conform proiectului.</p>
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

