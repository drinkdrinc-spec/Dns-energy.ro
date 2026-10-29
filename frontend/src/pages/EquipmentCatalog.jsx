import { useEffect, useMemo, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { F } from "@/components/cef/F";
import { Plus, Pencil, Trash2, Upload, FileText, X } from "lucide-react";
import { toast } from "sonner";

const CATS = ["Invertor", "Panou", "Baterie", "Smart meter"];
const FIELDS = {
  Invertor: [["type", "Tip", ["Hibrid", "On-grid", "Invertor de baterie (AC)"]], ["phases", "Faze", ["Trifazat", "Monofazat"]], ["p_nom_kw", "Pn (kW)"], ["p_max_kw", "Pmax (kW)"],
    ["vdc_max", "Udc max (V)"], ["mppt_min", "MPPT min (V)"], ["mppt_max", "MPPT max (V)"], ["mppt_count", "Nr. MPPT"], ["imax_mppt", "Imax / MPPT (A)"], ["battery_voltage", "Tensiune baterie compatibilă", null, "text"]],
  Panou: [["w", "Putere (W)"], ["voc", "Voc (V)"], ["vmp", "Vmp (V)"], ["isc", "Isc (A)"], ["imp", "Imp (A)"], ["coef_voc", "Coef. Voc (%/°C)"], ["coef_vmp", "Coef. Vmp (%/°C)"], ["temp_noct", "NOCT (°C)"], ["temp_pmax", "Coef. Pmax (%/°C)"]],
  Baterie: [["kwh", "kWh / modul"], ["ah", "Ah"], ["voltage", "Tensiune (V)"], ["tech", "Tehnologie", ["LV", "HV"]], ["coupling", "Cuplare", ["DC", "AC"]]],
  "Smart meter": [["phases", "Faze", ["Trifazat", "Monofazat"]]],
};
const spec = (i) => i.category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || ""} · ${i.type || ""}` : i.category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V` : i.category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.ah || "—"} Ah · ${i.voltage ?? "—"} V` : i.phases || "";

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
  return (
    <span className="inline-flex items-center gap-1">
      <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={up} data-testid={`upload-${k}-${item.id}`} />
      {f ? <a href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-bold" style={{ color: "var(--blue)" }} data-testid={`open-${k}-${item.id}`}><FileText size={13} /> {label}</a>
        : <span className="text-[12px]" style={{ color: "#b9770e" }}>{label} lipsă</span>}
      <button onClick={() => ref.current.click()} className="p-1 rounded hover:bg-[#eef4ff]" title={`Încarcă ${label}`} data-testid={`btn-upload-${k}-${item.id}`}><Upload size={13} style={{ color: "var(--blue)" }} /></button>
    </span>
  );
}

export default function EquipmentCatalog() {
  const [items, setItems] = useState([]);
  const [cat, setCat] = useState("Invertor");
  const [q, setQ] = useState("");
  const [form, setForm] = useState(null);
  const load = () => api.get("/data/catalog").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const rows = useMemo(() => items.filter((i) => i.category === cat && (!q || i.brand_model?.toLowerCase().includes(q.toLowerCase()))), [items, cat, q]);

  const save = async () => {
    if (!form.brand_model) return toast.error("Completează marca și modelul");
    const { id, ...rest } = form;
    if (id) await api.put(`/data/catalog/${id}`, rest); else await api.post("/data/catalog", { ...rest, category: cat });
    toast.success("Salvat"); setForm(null); load();
  };
  const remove = async (id) => { if (!window.confirm("Ștergi modelul din catalog?")) return; await api.delete(`/data/catalog/${id}`); load(); };

  return (
    <div>
      <PageHeader eyebrow="Bibliotecă echipamente" title="Catalog echipamente"
        sub="Modele cu date electrice, fișe tehnice și declarații de conformitate, reutilizate în configurarea CEF și în dosarele clienților."
        action={<Btn onClick={() => setForm(form ? null : { category: cat })} data-testid="catalog-add-btn">{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> Model nou</>}</Btn>} />
      <div className="flex flex-wrap gap-2 mb-4">
        {CATS.map((c) => <button key={c} onClick={() => { setCat(c); setForm(null); }} data-testid={`catalog-tab-${c}`}
          className="rounded-full px-4 py-2 text-[12px] font-bold border transition-colors" style={c === cat ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>{c}</button>)}
      </div>
      {form && (
        <div className="den-panel mb-6" data-testid="catalog-form">
          <h2 className="text-lg font-bold mb-4">{form.id ? "Editează modelul" : `Model nou — ${cat}`}</h2>
          <div className="grid sm:grid-cols-3 gap-3">
            <F label="Marcă și model *" value={form.brand_model} onChange={(v) => setForm({ ...form, brand_model: v })} testid="cat-field-brand_model" className="sm:col-span-2" />
            {FIELDS[form.category || cat].map(([k, l, opts, t]) => <F key={k} label={l} value={form[k]} options={opts || undefined} type={opts ? undefined : (t || "number")} onChange={(v) => setForm({ ...form, [k]: v })} testid={`cat-field-${k}`} />)}
            <F label="Observații" value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} testid="cat-field-notes" className="sm:col-span-3" />
          </div>
          <div className="flex gap-2 mt-5"><Btn onClick={save} data-testid="catalog-save-btn">Salvează</Btn><Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn></div>
          {!form.id && <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>După salvare poți încărca fișa tehnică și declarația de conformitate din listă.</p>}
        </div>
      )}
      <div className="den-panel">
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <h2 className="text-lg font-bold">{cat} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({rows.length})</span></h2>
          <input className="den-input" style={{ width: 240 }} placeholder="Caută model..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="catalog-db-search" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="catalog-table">
            <thead><tr className="text-left" style={{ background: "#f8fafd", color: "var(--muted)" }}>
              {["Model", "Specificații", "Documente", ""].map((h) => <th key={h} className="px-3 py-2.5 font-semibold text-[12px]">{h}</th>)}
            </tr></thead>
            <tbody>
              {rows.map((i) => (
                <tr key={i.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`catalog-row-${i.id}`}>
                  <td className="px-3 py-3 font-bold">{i.brand_model}{i.notes && <div className="text-[11px] font-normal" style={{ color: "var(--muted)" }}>{i.notes}</div>}</td>
                  <td className="px-3 py-3 whitespace-nowrap">{spec(i)}</td>
                  <td className="px-3 py-3"><div className="flex flex-col gap-1">
                    <DocSlot item={i} k="datasheet" label="Fișă tehnică" onUploaded={load} />
                    <DocSlot item={i} k="conformity" label="Declarație conformitate" onUploaded={load} />
                  </div></td>
                  <td className="px-3 py-3 text-right whitespace-nowrap">
                    <button onClick={() => setForm({ ...i })} className="p-1.5 rounded hover:bg-[#eef4ff]" data-testid={`catalog-edit-${i.id}`}><Pencil size={15} style={{ color: "var(--blue)" }} /></button>
                    <button onClick={() => remove(i.id)} className="p-1.5 rounded hover:bg-[#fff0f0] ml-1" data-testid={`catalog-delete-${i.id}`}><Trash2 size={15} style={{ color: "#b33333" }} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
