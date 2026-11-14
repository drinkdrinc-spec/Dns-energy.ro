import { Trash2 } from "lucide-react";
import { F, Check, CatalogPick, INSTALL, SECTIONS } from "./F";
import { Issues } from "./CefResults";

function Section({ title, children }) {
  return <div className="mt-4"><div className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--blue)" }}>{title}</div>{children}</div>;
}

export function InverterCard({ idx, inv, set, remove, catalog, shared, res }) {
  const s = (k) => (v) => set({ ...inv, [k]: v });
  const sub = (obj, k) => (v) => set({ ...inv, [obj]: { ...(inv[obj] || {}), [k]: v } });
  const strings = inv.strings || [];
  const optimizer = inv.optimizer || {};
  const batteryAc = inv.battery_charger || String(inv.type || inv.kind || "").includes("Invertor de baterie");
  const hasPv = !inv.no_panels && !batteryAc;
  const setStr = (i, k, v) => set({ ...inv, strings: strings.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  const setStringCount = (value) => {
    const count = Math.max(0, Math.min(24, Number(value) || 0));
    set({ ...inv, strings: Array.from({ length: count }, (_, i) => strings[i] || { panels: "", mppt: i + 1 }) });
  };
  const t = `inv-${idx}`;
  const pa = res?.proposals?.ac || {}, pd = res?.proposals?.dc || {};
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid={t}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h4 className="font-bold text-sm">Invertor {idx + 1} {res && <span className="font-normal text-xs" style={{ color: "var(--muted)" }}>· {res.kwp} kWp · DC/AC {res.dc_ac_ratio}{res.battery_kwh ? ` · ${res.battery_kwh} kWh` : ""}</span>}</h4>
        <button onClick={remove} className="p-1.5 rounded hover:bg-[#fff0f0]" data-testid={`${t}-remove`} title="Elimină invertorul"><Trash2 size={15} style={{ color: "#b33333" }} /></button>
      </div>
      <div className="mb-3 grid sm:grid-cols-2 gap-2">
        <Check label="Existent (rămâne în funcțiune)" value={inv.existing} onChange={s("existing")} testid={`${t}-existing`} />
        <Check label="Invertor-încărcător de baterie (ex. MultiPlus / Quattro)" value={inv.battery_charger} onChange={(value) => set({ ...inv, battery_charger: value, type: value ? "Invertor de baterie (AC)" : (inv.type === "Invertor de baterie (AC)" ? "Hibrid" : inv.type) })} testid={`${t}-battery-charger`} />
        <Check label="Fără panouri (doar baterie)" value={inv.no_panels} onChange={s("no_panels")} testid={`${t}-no-panels`} />
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <CatalogPick items={catalog} category="Invertor" selectedId={inv.catalog_id} selectedLabel={inv.brand_model} label="Model invertor" testid={`${t}-pick`} onManual={(model) => set({ ...inv, catalog_id: "", brand_model: model, type: "", phases: "", p_nom_kw: "", p_max_kw: "", vdc_max: "", mppt_min: "", mppt_max: "", mppt_count: "", imax_mppt: "", imax_mppt_values: [], isc_mppt_max: "", isc_mppt_max_values: [], bat_v_min: "", bat_v_max: "", bat_i_max: "" })} onPick={(it) => set({ ...inv, catalog_id: it.id, brand_model: it.brand_model, type: it.type, phases: it.phases, p_nom_kw: it.p_nom_kw, p_max_kw: it.p_max_kw, vdc_max: it.vdc_max, mppt_min: it.mppt_min, mppt_max: it.mppt_max, mppt_count: it.mppt_count, imax_mppt: it.imax_mppt, imax_mppt_values: it.imax_mppt_values || [], isc_mppt_max: it.isc_mppt_max, isc_mppt_max_values: it.isc_mppt_max_values || [], bat_v_min: it.bat_v_min, bat_v_max: it.bat_v_max, bat_i_max: it.bat_i_max })} />
        <F label="Putere invertor (kW)" type="number" value={inv.p_nom_kw} onChange={s("p_nom_kw")} testid={`${t}-pnom`} />
      </div>
      <details className="mt-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer text-xs font-bold" style={{ color: "var(--muted)" }}>Detalii tehnice invertor (opțional pentru previzualizare)</summary>
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Selectați modelul din catalog pentru completare automată. Datele tehnice se confirmă la aprobarea finală.</p>
        <div className="grid sm:grid-cols-4 gap-3 mt-3">
        <F label="Model introdus manual" value={inv.brand_model} onChange={s("brand_model")} testid={`${t}-model`} />
        <F label="Tip" value={inv.type} onChange={s("type")} options={["Hibrid", "On-grid", "Invertor de baterie (AC)"]} testid={`${t}-type`} />
        <F label="Faze" value={inv.phases} onChange={s("phases")} options={["Trifazat", "Monofazat"]} testid={`${t}-phases`} />
        {inv.phases === "Monofazat" && <F label="Faza de racord" value={inv.phase} onChange={s("phase")} options={["L1", "L2", "L3"]} testid={`${t}-phase`} />}
        <F label="Putere maximă (kW)" type="number" value={inv.p_max_kw} onChange={s("p_max_kw")} testid={`${t}-pmax`} />
        <F label="Limitare configurată (kW)" type="number" value={inv.p_limit_kw} onChange={s("p_limit_kw")} testid={`${t}-plim`} />
        <F label="Udc max (V)" type="number" value={inv.vdc_max} onChange={s("vdc_max")} testid={`${t}-vdc`} />
        <F label="MPPT min (V)" type="number" value={inv.mppt_min} onChange={s("mppt_min")} testid={`${t}-mpptmin`} />
        <F label="MPPT max (V)" type="number" value={inv.mppt_max} onChange={s("mppt_max")} testid={`${t}-mpptmax`} />
        <F label="Nr. MPPT" type="number" value={inv.mppt_count} onChange={s("mppt_count")} testid={`${t}-mpptn`} />
        {inv.type !== "On-grid" && <>
          <F label="Baterie: U min invertor (V)" type="number" value={inv.bat_v_min} onChange={s("bat_v_min")} testid={`${t}-batvmin`} />
          <F label="Baterie: U max invertor (V)" type="number" value={inv.bat_v_max} onChange={s("bat_v_max")} testid={`${t}-batvmax`} />
          <F label="Baterie: I max încărcare/descărcare invertor (A)" type="number" value={inv.bat_i_max} onChange={s("bat_i_max")} testid={`${t}-batimax`} />
        </>}
        <F label="Curent max/MPPT (A)" type="number" value={inv.imax_mppt} onChange={s("imax_mppt")} testid={`${t}-imax`} />
        <F label="Isc maxim / MPPT (A)" type="number" value={inv.isc_mppt_max} onChange={s("isc_mppt_max")} testid={`${t}-iscmax`} />
      </div>
      </details>

      {hasPv && <Section title="Panouri și stringuri">
        <div className="grid sm:grid-cols-2 gap-3">
          <CatalogPick items={catalog} category="Panou" selectedId={inv.panel_catalog_id} selectedLabel={inv.panel_model} label="Model panou" testid={`${t}-panel-pick`} onManual={(model) => set({ ...inv, panel_catalog_id: "", panel_model: model, panel_w: "", panel_voc: "", panel_vmp: "", panel_isc: "", panel_imp: "", panel_coef_voc: "", panel_coef_vmp: "" })} onPick={(it) => set({ ...inv, panel_catalog_id: it.id, panel_model: it.brand_model, panel_w: it.w, panel_voc: it.voc, panel_vmp: it.vmp, panel_isc: it.isc, panel_imp: it.imp, panel_coef_voc: it.coef_voc, panel_coef_vmp: it.coef_vmp })} />
          <F label="Putere panou (W)" type="number" value={inv.panel_w} onChange={s("panel_w")} testid={`${t}-panel-w`} />
        </div>
        <details className="mt-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
          <summary className="cursor-pointer text-xs font-bold" style={{ color: "var(--muted)" }}>Detalii tehnice panou (opțional pentru previzualizare)</summary>
          <div className="grid sm:grid-cols-4 gap-3 mt-3">
          <F label="Model introdus manual" value={inv.panel_model} onChange={s("panel_model")} testid={`${t}-panel-model`} />
          <F label="Coef. Voc (%/°C)" type="number" value={inv.panel_coef_voc} onChange={s("panel_coef_voc")} testid={`${t}-panel-coef`} />
          <F label="Voc (V)" type="number" value={inv.panel_voc} onChange={s("panel_voc")} testid={`${t}-panel-voc`} />
          <F label="Vmp (V)" type="number" value={inv.panel_vmp} onChange={s("panel_vmp")} testid={`${t}-panel-vmp`} />
          <F label="Isc (A)" type="number" value={inv.panel_isc} onChange={s("panel_isc")} testid={`${t}-panel-isc`} />
          </div>
        </details>
        <div className="mt-3 space-y-2">
          <F label="Număr stringuri" type="number" value={strings.length} onChange={setStringCount} testid={`${t}-string-count`} />
          {strings.map((st, i) => {
            const r = res?.strings?.[i];
            return (
              <div key={i} className="flex flex-wrap items-end gap-2" data-testid={`${t}-string-${i}`}>
                <span className="text-xs font-bold w-16 pb-3">String {i + 1}</span>
                <F label="Panouri pe string" type="number" value={st.panels} onChange={(v) => setStr(i, "panels", v)} testid={`${t}-string-${i}-panels`} />
                {r && <span className="text-xs pb-3" style={{ color: "var(--muted)" }}>Voc rece {r.voc_cold} V · Vmp {r.vmp_stc} V · {r.kwp} kWp</span>}
                <button onClick={() => set({ ...inv, strings: strings.filter((_, j) => j !== i) })} className="p-1.5 mb-1.5 rounded hover:bg-[#fff0f0]" data-testid={`${t}-string-${i}-remove`}><Trash2 size={14} style={{ color: "#b33333" }} /></button>
              </div>
            );
          })}
        </div>
      </Section>}

      <Section title="Baterie">
        <div className="grid sm:grid-cols-4 gap-3">
          <F label="Baterie" value={inv.battery_mode || "none"} onChange={(v) => set({ ...inv, battery_mode: v, ...(v === "shared" && !inv.shared_battery_id && shared.length === 1 ? { shared_battery_id: shared[0].id } : {}) })} options={[["none", "Nu"], ["own", "Da"], ["shared", "Baterie comună"]]} testid={`${t}-bat-mode`} />
          {inv.battery_mode === "shared" && <F label="Baterie comună" value={inv.shared_battery_id} onChange={s("shared_battery_id")} options={shared.map((b, i) => [b.id, b.model || `Baterie comună ${i + 1}`])} testid={`${t}-bat-shared`} />}
          {inv.battery_mode === "own" && <>
          <CatalogPick items={catalog} category="Baterie" selectedId={inv.battery?.catalog_id} selectedLabel={inv.battery?.model} label="Model baterie" testid={`${t}-bat-pick`} onManual={(model) => set({ ...inv, battery: { ...(inv.battery || {}), catalog_id: "", model, kwh: "", ah: "", voltage: "", voltage_min: "", voltage_max: "", voltage_ranges: [], i_max: "", coupling: "", modules: inv.battery?.modules || 1 } })} onPick={(it) => set({ ...inv, battery: { ...(inv.battery || {}), catalog_id: it.id, model: it.brand_model, kwh: it.kwh, ah: it.ah, voltage: it.voltage, voltage_min: it.voltage_min, voltage_max: it.voltage_max, voltage_ranges: it.voltage_ranges || [], i_max: it.i_max, coupling: it.coupling || "DC", modules: inv.battery?.modules || 1 } })} />
            <F label="Nr. module baterie" type="number" value={inv.battery?.modules} onChange={sub("battery", "modules")} testid={`${t}-bat-modules`} />
            <F label="Cuplaj baterie" value={inv.battery?.coupling || "DC"} onChange={sub("battery", "coupling")} options={["DC", "AC"]} testid={`${t}-bat-coupling-visible`} />
          </>}
          <div className="sm:col-span-2">
            <F label="Optimizatoare" value={optimizer.mode === "manual" ? "manual" : optimizer.catalog_id || "none"} options={[["none", "Fără optimizatoare"], ["manual", "Introduc manual modelul"], ...catalog.filter((item) => item.category === "Optimizator").map((item) => [item.id, item.brand_model])]} onChange={(id) => {
              if (id === "none") set({ ...inv, optimizer: { mode: "none", catalog_id: "", model: "" } });
              else if (id === "manual") set({ ...inv, optimizer: { ...optimizer, mode: "manual", catalog_id: "", model: optimizer.model || "" } });
              else { const item = catalog.find((entry) => entry.id === id); set({ ...inv, optimizer: { mode: "catalog", catalog_id: id, model: item?.brand_model || "" } }); }
            }} testid={`${t}-optimizer`} />
            {optimizer.mode === "manual" ? <F label="Model optimizator" value={optimizer.model} onChange={(model) => set({ ...inv, optimizer: { ...optimizer, mode: "manual", catalog_id: "", model } })} testid={`${t}-optimizer-model`} /> : null}
          </div>
        </div>
      </Section>

      <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer text-xs font-bold" style={{ color: "var(--muted)" }}>Detalii pentru verificarea tehnică (opțional pentru previzualizare)</summary>
        <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Secțiunile și protecțiile se propun automat. Lungimile cablurilor și măsurătorile se confirmă înainte de aprobarea finală.</p>
        <Section title="Stocare și backup">
        <div className="grid sm:grid-cols-4 gap-3">
          {inv.battery_mode === "own" && <>
            <F label="kWh / modul" type="number" value={inv.battery?.kwh} onChange={sub("battery", "kwh")} testid={`${t}-bat-kwh`} />
            <F label="Ah" type="number" value={inv.battery?.ah} onChange={sub("battery", "ah")} testid={`${t}-bat-ah`} />
            <F label="Tensiune (V)" type="number" value={inv.battery?.voltage} onChange={sub("battery", "voltage")} testid={`${t}-bat-v`} />
            <F label="Protecție baterie" value={inv.battery?.protection} onChange={sub("battery", "protection")} testid={`${t}-bat-prot`} />
            <F label="Curent max descărcare (A)" type="number" value={inv.battery?.i_max} onChange={sub("battery", "i_max")} testid={`${t}-bat-imax`} />
            <F label="Siguranță DC baterie (A)" type="number" value={inv.battery?.fuse_a} onChange={sub("battery", "fuse_a")} testid={`${t}-bat-fuse`} />
            <F label="Cablu baterie: secțiune (mm²)" type="number" value={inv.battery?.cable_section} onChange={sub("battery", "cable_section")} testid={`${t}-bat-cable`} />
            <F label="Cablu baterie: lungime (m)" type="number" value={inv.battery?.cable_length} onChange={sub("battery", "cable_length")} testid={`${t}-bat-cable-len`} />
          </>}
        </div>
        <div className="mt-3"><Check label="Circuit de backup / EPS" value={inv.backup?.enabled} onChange={sub("backup", "enabled")} testid={`${t}-backup`} /></div>
        {inv.backup?.enabled && (
          <div className="grid sm:grid-cols-3 gap-3 mt-2">
            <F label="Tip backup" value={inv.backup?.type} onChange={sub("backup", "type")} options={["parțial", "total"]} testid={`${t}-backup-type`} />
            <F label="Protecție backup" value={inv.backup?.breaker} onChange={sub("backup", "breaker")} testid={`${t}-backup-breaker`} />
            <F label="Circuite pe backup" value={inv.backup?.circuits} onChange={sub("backup", "circuits")} testid={`${t}-backup-circuits`} />
          </div>
        )}
      </Section>

      <Section title="Cabluri și protecții">
        <div className="grid sm:grid-cols-4 gap-3">
          <F label="AC: tip cablu" value={inv.ac?.cable_type} onChange={sub("ac", "cable_type")} testid={`${t}-ac-type`} />
          <F label="AC: material" value={inv.ac?.material || "Cu"} onChange={sub("ac", "material")} options={["Cu", "Al"]} testid={`${t}-ac-mat`} />
          <F label="AC: mod de pozare" value={inv.ac?.install || "C"} onChange={sub("ac", "install")} options={INSTALL} testid={`${t}-ac-install`} />
          <F label="AC: lungime (m)" type="number" value={inv.ac?.length_m} onChange={sub("ac", "length_m")} testid={`${t}-ac-len`} />
          <F label={`AC: secțiune (mm²)${pa.section ? ` · propus ${pa.section}` : ""}`} value={inv.ac?.section} onChange={(v) => sub("ac", "section")(Number(v))} options={SECTIONS} testid={`${t}-ac-section`} />
          <F label={`AC: disjunctor (A)${pa.breaker_a ? ` · Ib ${pa.ib} A, propus ${pa.breaker_a}` : ""}`} type="number" value={inv.ac?.breaker_a} onChange={sub("ac", "breaker_a")} testid={`${t}-ac-breaker`} />
          <F label="Factor corecție (grupare/temp.)" type="number" value={inv.ac?.k_correction} onChange={sub("ac", "k_correction")} testid={`${t}-ac-k`} />
          <F label="Diferențial invertor" value={inv.rcd} onChange={s("rcd")} testid={`${t}-rcd`} />
          <F label="Tip DDR (din manualul invertorului)" value={inv.rcd_type} onChange={s("rcd_type")} options={["Tip A", "Tip F", "Tip B", "Nu este cerut de producător"]} testid={`${t}-rcd-type`} />
          <F label="DDR IΔn (mA)" type="number" value={inv.rcd_ma} onChange={s("rcd_ma")} testid={`${t}-rcd-ma`} />
          <F label="AC: secțiune PE (mm²)" type="number" value={inv.ac?.pe_section} onChange={sub("ac", "pe_section")} testid={`${t}-ac-pe`} />
          <F label="AC: Icu întreruptor (kA)" type="number" value={inv.ac?.icu_ka} onChange={sub("ac", "icu_ka")} testid={`${t}-ac-icu`} />
          <F label="DC: tip cablu" value={inv.dc?.cable_type} onChange={sub("dc", "cable_type")} testid={`${t}-dc-type`} />
          <F label="DC: lungime (m)" type="number" value={inv.dc?.length_m} onChange={sub("dc", "length_m")} testid={`${t}-dc-len`} />
          <F label={`DC: secțiune (mm²)${pd.section ? ` · propus ${pd.section}` : ""}`} value={inv.dc?.section} onChange={(v) => sub("dc", "section")(Number(v))} options={SECTIONS.slice(1)} testid={`${t}-dc-section`} />
          <F label={`SPD DC Ucpv (V)${pd.spd_ucpv ? ` · propus ${pd.spd_ucpv}` : ""}`} type="number" value={inv.dc?.spd_ucpv} onChange={sub("dc", "spd_ucpv")} testid={`${t}-dc-spd`} />
          <F label="Siguranțe gPV (A)" type="number" value={inv.dc?.fuse_a} onChange={sub("dc", "fuse_a")} testid={`${t}-dc-fuse`} />
          <F label="Separator DC" value={inv.dc?.switch} onChange={sub("dc", "switch")} testid={`${t}-dc-switch`} />
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <span className="text-xs font-bold" style={{ color: "var(--green)" }}>Valorile calculate se completează automat în câmpurile goale.</span>
          {pd.fuse_note && <span className="text-xs" style={{ color: "var(--muted)" }}>Siguranțe gPV: {pd.fuse_note}</span>}
        </div>
      </Section>
      <Issues errors={res?.errors} warnings={res?.warnings} testid={`${t}-issues`} />
      </details>
    </div>
  );
}
