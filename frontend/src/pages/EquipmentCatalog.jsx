import { useEffect, useMemo, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { F } from "@/components/cef/F";
import { Plus, Pencil, Trash2, Upload, FileText, X, Search, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";

const CATS = [
  { value: "Invertor", label: "Invertoare" }, { value: "Panou", label: "Panouri" },
  { value: "Baterie", label: "Baterii" }, { value: "Smart meter", label: "Smart metere" },
  { value: "Gateway", label: "Gateways" }, { value: "Optimizator", label: "Optimizatoare" },
];
const FIELDS = {
  Invertor: [["type", "Tip", ["Hibrid", "On-grid", "Invertor de baterie (AC)"]], ["phases", "Faze", ["Trifazat", "Monofazat"]], ["p_nom_kw", "Pn (kW)"], ["p_max_kw", "Pmax (kW)"], ["vdc_max", "Udc max (V)"], ["mppt_min", "MPPT min (V)"], ["mppt_max", "MPPT max (V)"], ["mppt_count", "Nr. MPPT"], ["imax_mppt", "Imax / MPPT (A)"], ["isc_mppt_max", "Isc max / MPPT (A)"], ["battery_voltage", "Tensiune baterie compatibilă", null, "text"], ["bat_v_min", "Baterie: U min invertor (V)"], ["bat_v_max", "Baterie: U max invertor (V)"], ["bat_i_max", "Baterie: I max invertor (A)"]],
  Panou: [["w", "Putere (W)"], ["voc", "Voc (V)"], ["vmp", "Vmp (V)"], ["isc", "Isc (A)"], ["imp", "Imp (A)"], ["coef_voc", "Coef. Voc (%/°C)"], ["coef_vmp", "Coef. Vmp (%/°C)"], ["temp_noct", "NOCT (°C)"], ["temp_pmax", "Coef. Pmax (%/°C)"]],
  Baterie: [["kwh", "kWh / modul"], ["ah", "Ah"], ["voltage", "Tensiune nominală (V)"], ["voltage_min", "Tensiune minimă operare (V)"], ["voltage_max", "Tensiune maximă operare (V)"], ["i_max", "Curent max. încărcare/descărcare (A)"], ["tech", "Tehnologie", ["LV", "HV"]], ["coupling", "Cuplare", ["DC", "AC"]]],
  "Smart meter": [["phases", "Faze", ["Trifazat", "Monofazat"]], ["protocol", "Protocol", null, "text"], ["ct_ratio", "Raport TC", null, "text"]],
  Gateway: [["protocol", "Protocol", null, "text"], ["compatible", "Echipamente compatibile", null, "text"]],
  Optimizator: [["p_nom_kw", "Putere modul (W)"], ["voltage", "Tensiune max. (V)"], ["compatible", "Compatibilitate", null, "text"]],
};
const SOURCE_FIELDS = [["spec_source_url", "URL fișă oficială", null, "text"], ["spec_verified_at", "Verificat la", null, "text"]];
const spec = (i) => i.category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || "faze neprecizate"} · ${i.type || "tip neprecizat"}`
  : i.category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V`
    : i.category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.ah || "—"} Ah · ${i.tech || "LV/HV nespecificat"}`
      : `${i.phases || i.protocol || "Specificații de completat"}`;
const measuredAmount = (i) => i.category === "Invertor" ? Number(i.p_nom_kw) : i.category === "Panou" ? Number(i.w) : i.category === "Baterie" ? Number(i.kwh) : 0;

function DocSlot({ item, k, label, onUploaded }) {
  const ref = useRef();
  const f = item[k];
  const up = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      await api.put(`/data/catalog/${item.id}`, { [k]: data });
      toast.success(`${label} încărcată`); onUploaded();
    } catch { toast.error("Eroare la încărcare"); } finally { ref.current.value = ""; }
  };
  return <span className="inline-flex items-center gap-1.5">
    <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={up} data-testid={`upload-${k}-${item.id}`} />
    {f ? <a href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border bg-white px-3 text-[11px] font-medium" style={{ borderColor: "var(--line)", color: "var(--ink)" }} data-testid={`open-${k}-${item.id}`}><FileText size={13} /> {label}</a>
      : <button type="button" disabled className="inline-flex min-h-9 cursor-not-allowed items-center gap-1.5 rounded-lg border bg-white px-3 text-[11px] font-medium opacity-40" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid={`open-${k}-${item.id}`}><FileText size={13} /> {label}</button>}
    <button onClick={() => ref.current.click()} className="rounded p-1 hover:bg-[#eef4ff]" title={`${f ? "Înlocuiește" : "Încarcă"} ${label}`} aria-label={`${f ? "Înlocuiește" : "Încarcă"} ${label}`} data-testid={`btn-upload-${k}-${item.id}`}><Upload size={13} style={{ color: "var(--green)" }} /></button>
  </span>;
}

export default function EquipmentCatalog() {
  const [items, setItems] = useState([]);
  const [cat, setCat] = useState("Invertor");
  const [q, setQ] = useState("");
  const [minKw, setMinKw] = useState("");
  const [maxKw, setMaxKw] = useState("");
  const [phases, setPhases] = useState("");
  const [systemType, setSystemType] = useState("");
  const [docStatus, setDocStatus] = useState("all");
  const [form, setForm] = useState(null);
  const filterUnit = cat === "Panou" ? "W" : cat === "Baterie" ? "kWh" : "kW";
  const load = () => api.get("/data/catalog").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const rows = useMemo(() => items.filter((i) => {
    const docComplete = !!i.datasheet && !!i.conformity;
    const amount = measuredAmount(i);
    return i.category === cat && (!q || `${i.brand_model || ""} ${i.notes || ""}`.toLowerCase().includes(q.toLowerCase()))
      && (!minKw || amount >= Number(minKw)) && (!maxKw || amount <= Number(maxKw))
      && (!phases || i.phases === phases) && (!systemType || i.type === systemType)
      && (docStatus === "all" || (docStatus === "complete" ? docComplete : !docComplete));
  }), [items, cat, q, minKw, maxKw, phases, systemType, docStatus]);
  const completeCount = rows.filter((i) => i.datasheet && i.conformity).length;

  const save = async () => {
    if (!form.brand_model?.trim()) return toast.error("Completează marca și modelul");
    const { id, ...rest } = form;
    try {
      if (id) await api.put(`/data/catalog/${id}`, rest); else await api.post("/data/catalog", { ...rest, category: cat });
      toast.success("Salvat în catalog"); setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Modelul nu a putut fi salvat"); }
  };
  const remove = async (id) => { if (!window.confirm("Ștergi modelul din catalog?")) return; try { await api.delete(`/data/catalog/${id}`); load(); } catch { toast.error("Modelul nu a putut fi șters"); } };
  const clearFilters = () => { setQ(""); setMinKw(""); setMaxKw(""); setPhases(""); setSystemType(""); setDocStatus("all"); };

  return <div>
    <PageHeader eyebrow="Bibliotecă echipamente" title="Catalog echipamente" sub="Caută dispozitivele după categorie, putere, faze și tip. Fișele și declarațiile atașate pot fi folosite la generarea dosarului." action={<Btn onClick={() => setForm(form ? null : { category: cat })} data-testid="catalog-add-btn">{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> Adaugă</>}</Btn>} />
    <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Categorii echipamente">
      {CATS.map((c) => <button key={c.value} role="tab" aria-selected={cat === c.value} onClick={() => { setCat(c.value); setForm(null); }} data-testid={`catalog-tab-${c.value}`} className="rounded-xl border px-4 py-2.5 text-xs font-bold transition" style={cat === c.value ? { background: "var(--green)", color: "#fff", borderColor: "var(--green)" } : { background: "#fff", borderColor: "var(--line)", color: "var(--ink)" }}>{c.label}</button>)}
    </div>
    {form && <div className="den-panel mb-5" data-testid="catalog-form">
      <h2 className="mb-4 text-lg font-bold">{form.id ? "Editează modelul" : `Model nou — ${CATS.find((c) => c.value === cat)?.label || cat}`}</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <F label="Marcă și model *" value={form.brand_model} onChange={(v) => setForm({ ...form, brand_model: v })} testid="cat-field-brand_model" className="sm:col-span-2" />
        {[...(FIELDS[form.category || cat] || []), ...SOURCE_FIELDS].map(([k, l, opts, t]) => <F key={k} label={l} value={form[k]} options={opts || undefined} type={opts ? undefined : (t || "number")} onChange={(v) => setForm({ ...form, [k]: v })} testid={`cat-field-${k}`} />)}
        <F label="Observații" value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} testid="cat-field-notes" className="sm:col-span-3" />
      </div>
      <div className="mt-5 flex flex-wrap gap-2"><Btn onClick={save} data-testid="catalog-save-btn">Salvează</Btn><Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>{form.id && <Btn variant="secondary" onClick={() => remove(form.id)} data-testid={`catalog-delete-${form.id}`}><Trash2 size={14} /> Șterge modelul</Btn>}</div>
      {!form.id && <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>După salvare poți atașa fișa tehnică și declarația de conformitate.</p>}
    </div>}
    <section className="den-panel" data-testid="equipment-catalog-list">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-bold">{CATS.find((c) => c.value === cat)?.label} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>· {rows.length} rezultate</span></h2><p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>{completeCount} cu fișa tehnică și declarația de conformitate</p></div>
      </div>
      <div className="mb-4 rounded-xl p-3" style={{ background: "var(--bg)" }} data-testid="catalog-filters">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <label className="relative lg:col-span-2"><span className="sr-only">Caută marcă sau model</span><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} /><input className="den-input pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Caută marcă, model..." data-testid="catalog-db-search" /></label>
          <label className="flex items-center gap-1"><span className="sr-only">Putere minimă</span><input className="den-input" type="number" min="0" value={minKw} onChange={(e) => setMinKw(e.target.value)} placeholder="min" aria-label={`Putere minimă ${filterUnit}`} /><span className="text-[10px]">{filterUnit}</span></label>
          <label className="flex items-center gap-1"><span className="sr-only">Putere maximă</span><input className="den-input" type="number" min="0" value={maxKw} onChange={(e) => setMaxKw(e.target.value)} placeholder="max" aria-label={`Putere maximă ${filterUnit}`} /><span className="text-[10px]">{filterUnit}</span></label>
          <label><span className="sr-only">Faze</span><select className="den-input" value={phases} onChange={(e) => setPhases(e.target.value)} aria-label="Faze"><option value="">Mono + trifazat</option><option value="Monofazat">Monofazat</option><option value="Trifazat">Trifazat</option></select></label>
          <label><span className="sr-only">Tip invertor</span><select className="den-input" value={systemType} onChange={(e) => setSystemType(e.target.value)} aria-label="Tip"><option value="">Hibrid + on-grid</option><option value="Hibrid">Hibrid</option><option value="On-grid">On-grid</option></select></label>
          <label className="lg:col-span-2"><span className="sr-only">Completitudine documente</span><select className="den-input" value={docStatus} onChange={(e) => setDocStatus(e.target.value)} aria-label="Documente"><option value="all">Toate documentele</option><option value="complete">Documente complete</option><option value="missing">Documente lipsă</option></select></label>
          <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--muted)" }}><SlidersHorizontal size={14} /> Filtrează catalogul</div>
          {(q || minKw || maxKw || phases || systemType || docStatus !== "all") && <button className="text-left text-[11px] font-bold" style={{ color: "var(--green)" }} onClick={clearFilters}>Șterge filtrele</button>}
        </div>
      </div>
      <div className="space-y-2">
        {rows.map((i) => <article key={i.id} className="flex flex-col gap-3 rounded-xl border bg-white p-3 sm:flex-row sm:items-center" style={{ borderColor: "var(--line)" }} data-testid={`catalog-row-${i.id}`}>
          <div className="min-w-0 flex-1"><b className="block truncate text-sm">{i.brand_model}</b><span className="mt-1 block text-[11px]" style={{ color: "var(--muted)" }}>{spec(i)}{i.notes && i.notes !== "Date orientative — verificați fișa tehnică oficială a modelului exact." ? ` · ${i.notes}` : ""}</span>{i.spec_source_url && <a className="mt-1 inline-block text-[10px] font-bold" style={{ color: "var(--green)" }} href={i.spec_source_url} target="_blank" rel="noreferrer">Specificații verificate{i.spec_verified_at ? ` · ${i.spec_verified_at}` : ""} ↗</a>}</div>
          <div className="flex flex-wrap gap-x-3 gap-y-2"><DocSlot item={i} k="datasheet" label="Fișă tehnică" onUploaded={load} /><DocSlot item={i} k="conformity" label="Conformitate" onUploaded={load} /></div>
          <div className="flex shrink-0 gap-1"><button onClick={() => setForm({ ...i })} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border bg-white px-3 text-[11px] font-medium hover:bg-slate-50" style={{ borderColor: "var(--line)", color: "var(--ink)" }} title="Corectează modelul" data-testid={`catalog-edit-${i.id}`}><Pencil size={13} /> Corectează</button></div>
        </article>)}
        {!rows.length && <div className="rounded-xl py-10 text-center text-sm" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu sunt modele care să corespundă filtrelor. Adaugă un model în catalog și completează-i fișele.</div>}
      </div>
    </section>
  </div>;
}
