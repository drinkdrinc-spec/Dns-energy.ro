import { Trash2, Plus, Wand2 } from "lucide-react";
import { useEffect } from "react";
import { F, Check, CatalogPick, INSTALL, SECTIONS } from "./F";
import { Issues } from "./CefResults";
import { supplierPartnerPrice } from "@/lib/supplierPricing";

function Section({ title, children }) {
  return <div className="mt-4"><div className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--blue)" }}>{title}</div>{children}</div>;
}

function batteryVoltageForPhase(battery, phases) {
  return String(phases || "").toLowerCase().includes("tri")
    ? (battery?.voltage_3ph ?? battery?.voltage)
    : (battery?.voltage_1ph ?? battery?.voltage);
}

function batteryCatalogData(item, phases) {
  const breakerCurrent = item.breaker_a ?? item.dc_switch_current_a;
  const breakerVoltage = item.breaker_voltage_dc ?? item.dc_switch_voltage_v;
  return {
    catalog_id: item.id,
    model: item.brand_model,
    kwh: item.kwh,
    tech: item.tech,
    ah: item.ah,
    voltage: batteryVoltageForPhase(item, phases),
    voltage_1ph: item.voltage_1ph,
    voltage_3ph: item.voltage_3ph,
    i_max: item.i_max,
    i_max_source_url: item.i_max_source_url,
    max_fuse_a: item.max_fuse_a,
    coupling: item.coupling || "",
    breaker_a: breakerCurrent,
    breaker_voltage_dc: breakerVoltage,
    breaker_integrated: item.breaker_integrated,
    breaker_poles: item.breaker_poles,
    breaker_icu_ka: item.breaker_icu_ka,
    dc_switch_voltage_v: item.dc_switch_voltage_v ?? breakerVoltage,
    dc_switch_current_a: item.dc_switch_current_a ?? breakerCurrent,
    breaker_source_url: item.breaker_source_url,
    datasheet_url: item.datasheet_url,
    conformity_url: item.conformity_url,
  };
}

export function InverterCard({ idx, inv, set, remove, catalog, shared, res, supply, supplierMarkup = 15 }) {
  const s = (k) => (v) => set({ ...inv, [k]: v });
  const catalogModelText = (model, idKey, fields) => {
    const next = { ...inv, [idKey]: undefined };
    if (idKey === "catalog_id") next.brand_model = model;
    if (idKey === "panel_catalog_id") next.panel_model = model;
    fields.forEach((field) => { next[field] = undefined; });
    set(next);
  };
  const batteryModelText = (model) => set({
    ...inv,
    battery: { ...(inv.battery || {}), model, catalog_id: undefined, kwh: undefined, tech: undefined, ah: undefined, voltage: undefined, voltage_1ph: undefined, voltage_3ph: undefined, i_max: undefined, i_max_source_url: undefined, max_fuse_a: undefined, coupling: undefined, protection: undefined, fuse_a: undefined, cable_section: undefined, breaker_a: undefined, breaker_voltage_dc: undefined, breaker_integrated: undefined, breaker_poles: undefined, breaker_icu_ka: undefined, dc_switch_voltage_v: undefined, dc_switch_current_a: undefined, breaker_source_url: undefined, datasheet_url: undefined, conformity_url: undefined },
  });
  const sub = (obj, k) => (v) => set({ ...inv, [obj]: { ...(inv[obj] || {}), [k]: v } });
  const strings = inv.strings || [];
  const setStr = (i, k, v) => set({ ...inv, strings: strings.map((x, j) => (j === i ? { ...x, [k]: v, auto_generated: false } : x)) });
  const setStringPanel = (i, item) => {
    const models = new Set(strings.map((x, j) => j === i ? null : (x.panel_model || inv.panel_model)).filter(Boolean));
    models.add(item.brand_model);
    if (models.size > 3) return;
    set({ ...inv, strings: strings.map((x, j) => j === i ? {
      ...x, panel_catalog_id: item.id, panel_model: item.brand_model, panel_w: item.w,
      panel_voc: item.voc, panel_vmp: item.vmp, panel_isc: item.isc, panel_imp: item.imp,
      panel_coef_voc: item.coef_voc, panel_coef_vmp: item.coef_vmp,
    } : x) });
  };
  const stringPanelQuery = (i, model) => {
    const models = new Set(strings.map((x, j) => j === i ? null : (x.panel_model || inv.panel_model)).filter(Boolean));
    if (model && !models.has(model) && models.size >= 3) return;
    set({ ...inv, strings: strings.map((x, j) => j === i ? {
      ...x, panel_model: model, panel_catalog_id: undefined, panel_w: undefined, panel_voc: undefined,
      panel_vmp: undefined, panel_isc: undefined, panel_imp: undefined, panel_coef_voc: undefined, panel_coef_vmp: undefined,
    } : x) });
  };
  const t = `inv-${idx}`;
  const selectedEquipment = [
    catalog.find((item) => item.id === inv.catalog_id),
    catalog.find((item) => item.id === inv.panel_catalog_id),
    ...strings.map((row) => catalog.find((item) => item.id === row.panel_catalog_id)),
    inv.battery?.catalog_id ? catalog.find((item) => item.id === inv.battery.catalog_id) : null,
  ].filter(Boolean).filter((item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index);
  const pa = res?.proposals?.ac || {}, pd = res?.proposals?.dc || {};
  const selectedPhase = String(inv.phases || supply || "").toLowerCase();
  const isMono = selectedPhase.includes("mono");
  const isTri = selectedPhase.includes("tri");
  const acSections = isMono ? [6, 10, 16] : isTri ? [6, 10, 16, 25, 35, 50] : SECTIONS.filter((section) => section >= 6 && section <= 50);
  const apply = () => set({
    ...inv,
    ac: { ...(inv.ac || {}), breaker_a: inv.ac?.breaker_a || pa.breaker_a, section: inv.ac?.section || pa.section },
    dc: { ...(inv.dc || {}), section: inv.dc?.section || pd.section, spd_ucpv: inv.dc?.spd_ucpv || pd.spd_ucpv, fuse_a: inv.dc?.fuse_a || pd.fuse || "" },
  });
  useEffect(() => {
    const nextAc = { ...(inv.ac || {}) };
    const nextDc = { ...(inv.dc || {}) };
    if (!nextAc.breaker_a && pa.breaker_a) nextAc.breaker_a = pa.breaker_a;
    if (!nextAc.section && pa.section) nextAc.section = pa.section;
    if (!nextAc.cable_type && inv.p_nom_kw) nextAc.cable_type = "RV-K";
    if (!nextDc.section && pd.section) nextDc.section = pd.section;
    if (!nextDc.spd_ucpv && pd.spd_ucpv) nextDc.spd_ucpv = pd.spd_ucpv;
    if (!nextDc.fuse_a && pd.fuse) nextDc.fuse_a = pd.fuse;
    if (!nextDc.cable_type && strings.length) nextDc.cable_type = "H1Z2Z2-K";
    if (JSON.stringify(nextAc) !== JSON.stringify(inv.ac || {}) || JSON.stringify(nextDc) !== JSON.stringify(inv.dc || {})) {
      set({ ...inv, ac: nextAc, dc: nextDc });
    }
  }, [pa.breaker_a, pa.section, pd.section, pd.spd_ucpv, pd.fuse, inv.p_nom_kw, strings.length, inv.ac, inv.dc]);
  return (
    <div className="rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid={t}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h4 className="font-bold text-sm">{inv.type === "Invertor de baterie (AC)" ? `Invertor BESS ${idx + 1}` : `Invertor ${idx + 1}`} {res && <span className="font-normal text-xs" style={{ color: "var(--muted)" }}>· {res.kwp} kWp · DC/AC {res.dc_ac_ratio}{res.battery_kwh ? ` · ${res.battery_kwh} kWh` : ""}</span>}</h4>
        <button onClick={remove} className="p-1.5 rounded hover:bg-[#fff0f0]" data-testid={`${t}-remove`} title="Elimină invertorul"><Trash2 size={15} style={{ color: "#b33333" }} /></button>
      </div>
      {selectedEquipment.length > 0 && <div className="mb-3 space-y-1 rounded-lg p-2.5 text-[11px]" style={{ background: "var(--bg, #faf8f4)" }} data-testid={`${t}-equipment-documents-prices`}>
        {selectedEquipment.map((item) => <div key={item.id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-semibold">{item.category}: {item.brand_model}</span>
          {item.source_price && <span style={{ color: "var(--muted)" }}>Furnizor: {item.source_price}</span>}
          {supplierPartnerPrice(item.source_price, supplierMarkup) && <span className="font-bold" style={{ color: "var(--green, #168363)" }}>Orientativ DNS (+{supplierMarkup}%): {supplierPartnerPrice(item.source_price, supplierMarkup)} / unitate</span>}
          {item.datasheet_url && <a className="font-semibold underline" style={{ color: "var(--green, #168363)" }} href={item.datasheet_url} target="_blank" rel="noopener noreferrer">Fișă tehnică</a>}
          {item.conformity_url && <a className="font-semibold underline" style={{ color: "var(--green, #168363)" }} href={item.conformity_url} target="_blank" rel="noopener noreferrer">Conformitate</a>}
          {!item.datasheet_url && item.datasheet?.storage_path && <span style={{ color: "var(--green, #168363)" }}>Fișa tehnică este salvată în catalog</span>}
          {!item.conformity_url && item.conformity?.storage_path && <span style={{ color: "var(--green, #168363)" }}>Conformitatea este salvată în catalog</span>}
        </div>)}
      </div>}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <CatalogPick items={catalog} category="Invertor" selectedId={inv.catalog_id} testid={`${t}-pick`} onQueryChange={(model) => catalogModelText(model, "catalog_id", ["type", "phases", "p_nom_kw", "p_max_kw", "vdc_max", "mppt_min", "mppt_max", "mppt_count", "imax_mppt", "isc_max_mppt", "bat_i_max", "red_limit_mode"])} onPick={(it) => { const battery = inv.battery?.catalog_id ? { ...inv.battery, voltage: batteryVoltageForPhase(inv.battery, it.phases) } : inv.battery; set({ ...inv, ...(battery ? { battery } : {}), catalog_id: it.id, brand_model: it.brand_model, type: it.type, phases: it.phases, p_nom_kw: it.p_nom_kw, p_max_kw: it.p_max_kw, vdc_max: it.vdc_max, mppt_min: it.mppt_min, mppt_max: it.mppt_max, mppt_count: it.mppt_count, imax_mppt: it.imax_mppt, isc_max_mppt: it.isc_max_mppt, bat_i_max: it.bat_i_max, red_limit_mode: it.red_limit_mode || "Nu este declarată" }); }} />
        <F label="Marcă și model" value={inv.brand_model} onChange={(model) => catalogModelText(model, "catalog_id", ["type", "phases", "p_nom_kw", "p_max_kw", "vdc_max", "mppt_min", "mppt_max", "mppt_count", "imax_mppt", "isc_max_mppt", "bat_i_max", "red_limit_mode"])} testid={`${t}-model`} className="col-span-2" />
        <F label="Limită injecție în rețea (kW)" type="number" value={inv.p_limit_kw} onChange={s("p_limit_kw")} testid={`${t}-plim`} />
        <details className="col-span-2 sm:col-span-4 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-xs font-semibold">Detalii invertor · completate din fișa tehnică</summary><div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
        <F label="Tip" value={inv.type} onChange={s("type")} options={["Hibrid", "On-grid", "Invertor de baterie (AC)"]} testid={`${t}-type`} />
        <F label="Faze" value={inv.phases} onChange={s("phases")} options={["Trifazat", "Monofazat"]} testid={`${t}-phases`} />
        {inv.phases === "Monofazat" && <F label="Faza de racord" value={inv.phase} onChange={s("phase")} options={["L1", "L2", "L3"]} testid={`${t}-phase`} />}
        <F label="Putere nominală (kW)" type="number" value={inv.p_nom_kw} onChange={s("p_nom_kw")} testid={`${t}-pnom`} />
        <F label="Putere maximă (kW)" type="number" value={inv.p_max_kw} onChange={s("p_max_kw")} testid={`${t}-pmax`} />
        <F label="Limitare putere în RED" value={inv.red_limit_mode || "Nu este declarată"} onChange={s("red_limit_mode")} options={["Nu este declarată", "Limitare putere evacuată", "Zero export"]} testid={`${t}-red-limit-mode`} />
        <F label="Udc max (V)" type="number" value={inv.vdc_max} onChange={s("vdc_max")} testid={`${t}-vdc`} />
        <F label="MPPT min (V)" type="number" value={inv.mppt_min} onChange={s("mppt_min")} testid={`${t}-mpptmin`} />
        <F label="MPPT max (V)" type="number" value={inv.mppt_max} onChange={s("mppt_max")} testid={`${t}-mpptmax`} />
        <F label="Nr. MPPT" type="number" value={inv.mppt_count} onChange={s("mppt_count")} testid={`${t}-mpptn`} />
        {inv.type !== "On-grid" && <>
          <F label="Baterie: U min invertor (V)" type="number" value={inv.bat_v_min} onChange={s("bat_v_min")} testid={`${t}-batvmin`} />
          <F label="Baterie: U max invertor (V)" type="number" value={inv.bat_v_max} onChange={s("bat_v_max")} testid={`${t}-batvmax`} />
          <F label="Baterie: I max încărcare/descărcare invertor (A)" type="number" value={inv.bat_i_max} onChange={s("bat_i_max")} testid={`${t}-batimax`} />
        </>}
        <F label="Curent maxim de funcționare / MPPT (A)" type="number" value={inv.imax_mppt} onChange={s("imax_mppt")} testid={`${t}-imax`} />
          <F label="Isc maxim admisibil / MPPT (A)" type="number" value={inv.isc_max_mppt} onChange={s("isc_max_mppt")} testid={`${t}-iscmax`} />
        </div></details>
      </div>
      <div className="mt-2"><Check label="Echipament existent (extindere)" value={inv.existing} onChange={s("existing")} testid={`${t}-existing`} /></div>

      {!(inv.battery_only || inv.no_panels) && <Section title="Panouri și stringuri">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <CatalogPick items={catalog} category="Panou" selectedId={inv.panel_catalog_id} testid={`${t}-panel-pick`} onQueryChange={(model) => catalogModelText(model, "panel_catalog_id", ["panel_w", "panel_voc", "panel_vmp", "panel_isc", "panel_imp", "panel_coef_voc", "panel_coef_vmp"])} onPick={(it) => set({ ...inv, panel_catalog_id: it.id, panel_model: it.brand_model, panel_w: it.w, panel_voc: it.voc, panel_vmp: it.vmp, panel_isc: it.isc, panel_imp: it.imp, panel_coef_voc: it.coef_voc, panel_coef_vmp: it.coef_vmp })} />
          <F label="Model panou" value={inv.panel_model} onChange={(model) => catalogModelText(model, "panel_catalog_id", ["panel_w", "panel_voc", "panel_vmp", "panel_isc", "panel_imp", "panel_coef_voc", "panel_coef_vmp"])} testid={`${t}-panel-model`} />
          <F label="Putere panou (W)" type="number" value={inv.panel_w} onChange={s("panel_w")} testid={`${t}-panel-w`} />
          <details className="col-span-2 sm:col-span-4 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-xs font-semibold">Parametri panou din fișa tehnică</summary><div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
          <F label="Coef. Voc (%/°C)" type="number" value={inv.panel_coef_voc} onChange={s("panel_coef_voc")} testid={`${t}-panel-coef`} />
          <F label="Voc (V)" type="number" value={inv.panel_voc} onChange={s("panel_voc")} testid={`${t}-panel-voc`} />
          <F label="Vmp (V)" type="number" value={inv.panel_vmp} onChange={s("panel_vmp")} testid={`${t}-panel-vmp`} />
          <F label="Isc (A)" type="number" value={inv.panel_isc} onChange={s("panel_isc")} testid={`${t}-panel-isc`} />
          </div></details>
        </div>
        <div className="mt-3 space-y-2">
          {strings.map((st, i) => {
            const r = res?.strings?.[i];
            return (
              <div key={i} className="flex flex-wrap items-end gap-2" data-testid={`${t}-string-${i}`}>
                <span className="text-xs font-bold w-16 pb-3">String {i + 1}</span>
                <CatalogPick items={catalog} category="Panou" selectedId={st.panel_catalog_id} testid={`${t}-string-${i}-panel-pick`} label="Model panou · gol = modelul invertorului" onQueryChange={(model) => stringPanelQuery(i, model)} onPick={(item) => setStringPanel(i, item)} />
                <F label="Panouri în serie" type="number" value={st.panels} onChange={(v) => setStr(i, "panels", v)} testid={`${t}-string-${i}-panels`} />
                <span className="text-xs pb-3" style={{ color: "var(--muted)" }}>MPPT {st.mppt || i + 1}{r?.kwp ? ` · ${r.kwp} kWp` : ""}</span>
                <button onClick={() => set({ ...inv, strings: strings.filter((_, j) => j !== i) })} className="p-1.5 mb-1.5 rounded hover:bg-[#fff0f0]" data-testid={`${t}-string-${i}-remove`}><Trash2 size={14} style={{ color: "#b33333" }} /></button>
              </div>
            );
          })}
          <button onClick={() => set({ ...inv, strings: [...strings, { panels: "", mppt: strings.length + 1 }] })} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid={`${t}-add-string`}><Plus size={13} /> Adaugă string</button>
        </div>
      </Section>}

      <Section title="Stocare și backup">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <F label="Baterie" value={inv.battery_mode || "none"} onChange={(v) => set({ ...inv, battery_mode: v, ...(v === "shared" && !inv.shared_battery_id && shared.length === 1 ? { shared_battery_id: shared[0].id } : {}) })} options={[["none", "Fără baterie"], ["own", "Baterie proprie"], ["shared", "Baterie comună"]]} testid={`${t}-bat-mode`} />
          {inv.battery_mode === "shared" && <F label="Baterie comună" value={inv.shared_battery_id} onChange={s("shared_battery_id")} options={shared.map((b, i) => [b.id, b.model || `Baterie comună ${i + 1}`])} testid={`${t}-bat-shared`} />}
          {inv.battery_mode === "own" && <>
            <CatalogPick items={catalog} category="Baterie" selectedId={inv.battery?.catalog_id} testid={`${t}-bat-pick`} onQueryChange={batteryModelText} onPick={(it) => set({ ...inv, battery: { ...(inv.battery || {}), ...batteryCatalogData(it, inv.phases) } })} />
            <F label="Model baterie" value={inv.battery?.model} onChange={batteryModelText} testid={`${t}-bat-model`} />
            <F label="Conectare baterie la invertor" value={inv.battery?.coupling || ""} onChange={sub("battery", "coupling")} options={["DC"]} testid={`${t}-bat-coupling`} />
            <p className="col-span-2 sm:col-span-4 -mt-2 text-[11px] leading-4" style={{ color: "var(--muted)" }}>Bateria proprie se conectează în DC la invertorul selectat. Pentru BESS cuplată AC față de sistemul PV, adaugă un invertor BESS / PCS separat și configurează bateria ca „comună”.</p>
            <F label="kWh / modul" type="number" value={inv.battery?.kwh} onChange={sub("battery", "kwh")} testid={`${t}-bat-kwh`} />
            <F label="Nr. module" type="number" value={inv.battery?.modules} onChange={sub("battery", "modules")} testid={`${t}-bat-modules`} />
            <details className="col-span-2 sm:col-span-4 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-xs font-semibold">Alte date baterie din fișa tehnică</summary><div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <F label="Ah" type="number" value={inv.battery?.ah} onChange={sub("battery", "ah")} testid={`${t}-bat-ah`} />
            <F label="Tensiune (V)" type="number" value={inv.battery?.voltage} onChange={sub("battery", "voltage")} testid={`${t}-bat-v`} />

            <F label="Protecție baterie" value={inv.battery?.protection} onChange={sub("battery", "protection")} testid={`${t}-bat-prot`} />
            <F label="Curent max descărcare (A)" type="number" value={inv.battery?.i_max} onChange={sub("battery", "i_max")} testid={`${t}-bat-imax`} />
            <F label="Siguranță DC baterie (A)" type="number" value={inv.battery?.fuse_a} onChange={sub("battery", "fuse_a")} testid={`${t}-bat-fuse`} />
            <F label="Siguranță maximă admisă (A), din fișă" type="number" value={inv.battery?.max_fuse_a} onChange={sub("battery", "max_fuse_a")} testid={`${t}-bat-max-fuse`} />
            <F label="Separator DC: tensiune nominală (V)" type="number" value={inv.battery?.dc_switch_voltage_v ?? inv.battery?.breaker_voltage_dc} onChange={sub("battery", "dc_switch_voltage_v")} testid={`${t}-bat-dc-switch-voltage`} />
            <F label="Separator DC: curent nominal (A)" type="number" value={inv.battery?.dc_switch_current_a ?? inv.battery?.breaker_a} onChange={sub("battery", "dc_switch_current_a")} testid={`${t}-bat-dc-switch-current`} />
            <F label="Cablu baterie: secțiune (mm²)" type="number" value={inv.battery?.cable_section} onChange={sub("battery", "cable_section")} testid={`${t}-bat-cable`} />
            <F label="Cablu baterie: lungime (m)" type="number" value={inv.battery?.cable_length} onChange={sub("battery", "cable_length")} testid={`${t}-bat-cable-len`} />
            </div></details>
          </>}
        </div>
        <div className="mt-3"><Check label="Circuit de backup / EPS" value={inv.backup?.enabled} onChange={sub("backup", "enabled")} testid={`${t}-backup`} /></div>
        {inv.battery_mode === "own" && <div className="mt-2"><Check label="Fără panouri (doar baterie)" value={inv.battery_only || inv.no_panels} onChange={(enabled) => set({ ...inv, battery_only: enabled, no_panels: enabled, ...(enabled ? { saved_pv_strings: inv.strings || [], strings: [] } : { strings: inv.strings?.length ? inv.strings : (inv.saved_pv_strings || []) }) })} testid={`${t}-battery-only`} /></div>}
        {(inv.battery_only || inv.no_panels) && <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Invertorul rămâne desenat cu bateria, fără ramură PV; puterea evacuată în RED este 0 kW.</p>}
        {inv.backup?.enabled && (
          <details className="mt-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-xs font-semibold">Setări avansate circuit backup</summary><div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
            <F label="Tip backup" value={inv.backup?.type} onChange={sub("backup", "type")} options={["parțial", "total"]} testid={`${t}-backup-type`} />
            <F label="Protecție backup" value={inv.backup?.breaker} onChange={sub("backup", "breaker")} testid={`${t}-backup-breaker`} />
            <F label="Circuite pe backup" value={inv.backup?.circuits} onChange={sub("backup", "circuits")} testid={`${t}-backup-circuits`} />
          </div></details>
        )}
      </Section>

      <details className="mt-4 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}><summary className="cursor-pointer text-xs font-semibold">Detalii tehnice · cabluri, protecții și valori calculate</summary>
      <Section title="Cabluri și protecții">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <F label="AC: tip cablu" value={inv.ac?.cable_type} onChange={sub("ac", "cable_type")} testid={`${t}-ac-type`} />
          <F label="AC: material" value={inv.ac?.material || "Cu"} onChange={sub("ac", "material")} options={["Cu", "Al"]} testid={`${t}-ac-mat`} />
          <F label="AC: mod de pozare" value={inv.ac?.install || "C"} onChange={sub("ac", "install")} options={INSTALL} testid={`${t}-ac-install`} />
          <F label="AC: lungime (m)" type="number" value={inv.ac?.length_m} onChange={sub("ac", "length_m")} testid={`${t}-ac-len`} />
          <F label={`AC: secțiune (${isMono ? "3×" : isTri ? "5×" : "faze neconfirmate · 3×/5×"} mm²)${pa.section ? ` · propus ${pa.section}` : ""}`} value={inv.ac?.section} onChange={(v) => sub("ac", "section")(Number(v))} options={acSections} testid={`${t}-ac-section`} />
          <F label={`AC: disjunctor (A)${pa.breaker_a ? ` · Ib ${pa.ib} A, propus ${pa.breaker_a}` : ""}`} type="number" value={inv.ac?.breaker_a} onChange={sub("ac", "breaker_a")} testid={`${t}-ac-breaker`} />
          <F label="Factor corecție (grupare/temp.)" type="number" value={inv.ac?.k_correction} onChange={sub("ac", "k_correction")} testid={`${t}-ac-k`} />
          <F label="Diferențial invertor" value={inv.rcd} onChange={s("rcd")} testid={`${t}-rcd`} />
          <F label="Tip DDR (din manualul invertorului)" value={inv.rcd_type} onChange={s("rcd_type")} options={["Tip A", "Tip F", "Tip B", "Nu este cerut de producător"]} testid={`${t}-rcd-type`} />
          <F label="DDR IΔn (mA)" type="number" value={inv.rcd_ma} onChange={s("rcd_ma")} testid={`${t}-rcd-ma`} />
          <F label="AC: secțiune PE (mm²)" type="number" value={inv.ac?.pe_section} onChange={sub("ac", "pe_section")} testid={`${t}-ac-pe`} />
          <F label="AC: Icu întreruptor (kA)" type="number" value={inv.ac?.icu_ka} onChange={sub("ac", "icu_ka")} testid={`${t}-ac-icu`} />
          <F label="DC: tip cablu" value={inv.dc?.cable_type} onChange={sub("dc", "cable_type")} testid={`${t}-dc-type`} />
          <F label="DC: lungime (m)" type="number" value={inv.dc?.length_m} onChange={sub("dc", "length_m")} testid={`${t}-dc-len`} />
          <F label={`DC: secțiune (mm², H1Z2Z2-K ≥ 6)${pd.section ? ` · propus ${pd.section}` : ""}`} value={inv.dc?.section} onChange={(v) => sub("dc", "section")(Number(v))} options={SECTIONS.slice(3, 12)} testid={`${t}-dc-section`} />
          <F label={`SPD DC Ucpv (V)${pd.spd_ucpv ? ` · propus ${pd.spd_ucpv}` : ""}`} type="number" value={inv.dc?.spd_ucpv} onChange={sub("dc", "spd_ucpv")} testid={`${t}-dc-spd`} />
          <F label="Separator fuzibil gPV / string (A)" type="number" value={inv.dc?.fuse_a ?? 15} onChange={sub("dc", "fuse_a")} testid={`${t}-dc-fuse`} />
          <F label="Separator DC" value={inv.dc?.switch} onChange={sub("dc", "switch")} testid={`${t}-dc-switch`} />
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <button onClick={apply} className="text-xs font-bold inline-flex items-center gap-1 rounded-lg border px-3 py-2" style={{ color: "var(--blue)", borderColor: "var(--line)" }} data-testid={`${t}-apply`}><Wand2 size={13} /> Completează câmpurile goale cu valorile propuse</button>
          {pd.fuse_note && <span className="text-xs" style={{ color: "var(--muted)" }}>Siguranțe gPV: {pd.fuse_note}</span>}
        </div>
      </Section>
      </details>
      <Issues errors={res?.errors} warnings={res?.warnings} testid={`${t}-issues`} />
    </div>
  );
}


