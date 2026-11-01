import { useEffect, useMemo, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { F } from "@/components/cef/F";
import { Plus, Pencil, Trash2, Upload, FileText, X, Sparkles } from "lucide-react";
import { toast } from "sonner";

const CATS = ["Invertor", "Panou", "Baterie", "Smart meter"];
const FIELDS = {
  Invertor: [["type", "Tip", ["Hibrid", "On-grid", "Invertor de baterie (AC)"]], ["phases", "Faze", ["Trifazat", "Monofazat"]], ["p_nom_kw", "Pn (kW)"], ["p_max_kw", "Pmax (kW)"], ["red_limit_mode", "Limitare putere în RED", ["Nu este declarată", "Limitare putere evacuată", "Zero export"]],
    ["vdc_max", "Udc max (V)"], ["mppt_min", "MPPT min (V)"], ["mppt_max", "MPPT max (V)"], ["mppt_count", "Nr. MPPT"], ["imax_mppt", "Imax / MPPT (A)"], ["battery_voltage", "Tensiune baterie compatibilă", null, "text"]],
  Panou: [["w", "Putere (W)"], ["voc", "Voc (V)"], ["vmp", "Vmp (V)"], ["isc", "Isc (A)"], ["imp", "Imp (A)"], ["coef_voc", "Coef. Voc (%/°C)"], ["coef_vmp", "Coef. Vmp (%/°C)"], ["temp_noct", "NOCT (°C)"], ["temp_pmax", "Coef. Pmax (%/°C)"]],
  Baterie: [["kwh", "kWh / modul"], ["ah", "Ah"], ["voltage", "Tensiune (V)"], ["tech", "Tehnologie", ["LV", "HV"]], ["coupling", "Cuplare", ["DC", "AC"]]],
  "Smart meter": [["phases", "Faze", ["Trifazat", "Monofazat"]]],
};
const spec = (i) => i.category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || ""} · ${i.type || ""}` : i.category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V` : i.category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.ah || "—"} Ah · ${i.voltage ?? "—"} V` : i.phases || "";

function DocSlot({ item, k, label, onUploaded }) {
  const ref = useRef();
  const [sourceUrl, setSourceUrl] = useState(() => item[`${k}_source_url`] || item[`${k}_url`] || "");
  const officialUrl = item[`${k}_url`] || item[`${k}_source_url`] || "";
  const [importing, setImporting] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const f = item[k];
  const importUrl = async () => {
    setImporting(true);
    try {
      await api.post(`/catalog/${item.id}/import-document`, { kind: k, url: sourceUrl });
      toast.success(`${label} preluată de la sursa oficială`);
      setSourceUrl("");
      onUploaded();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Importul documentului a eșuat");
    } finally {
      setImporting(false);
    }
  };
  const extract = async () => {
    setExtracting(true);
    try {
      const { data } = await api.post(`/ai/catalog/${item.id}/extract`);
      const count = Object.keys(data.filled || {}).length;
      toast.success(count ? `${count} valori extrase din fișă; verifică-i înainte de folosire` : "Nu au fost găsite valori noi de completat");
      onUploaded();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Extragerea AI a eșuat");
    } finally {
      setExtracting(false);
    }
  };
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
      {f ? <a href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[12px] font-bold" style={{ color: "var(--blue)" }} data-testid={`open-${k}-${item.id}`} title={f.source_url || "Document încărcat"}><FileText size={13} /> {label}</a>
        : <span className="text-[12px]" style={{ color: "#b9770e" }}>{label} lipsă</span>}
      {officialUrl && <a href={officialUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] underline" title="Deschide documentul de la producător">Sursă oficială ↗</a>}
      <button onClick={() => ref.current.click()} className="p-1 rounded hover:bg-[#eef4ff]" title={`Încarcă ${label}`} data-testid={`btn-upload-${k}-${item.id}`}><Upload size={13} style={{ color: "var(--blue)" }} /></button>
      <input className="den-input text-[11px] py-1" style={{ width: 220 }} type="url" placeholder="Link PDF oficial HTTPS" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} aria-label={`Link oficial ${label}`} />
      <button onClick={importUrl} disabled={importing || !sourceUrl} className="text-[11px] font-bold px-2 py-1 rounded border disabled:opacity-50" title="Preia PDF de pe site-ul oficial" data-testid={`import-url-${k}-${item.id}`}>{importing ? "Se preia…" : "Importă PDF"}</button>
      {k === "datasheet" && f && <button onClick={extract} disabled={extracting} className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded border disabled:opacity-50" title="Extrage numai specificațiile care apar în fișa PDF" data-testid={`ai-extract-${item.id}`}><Sparkles size={12} /> {extracting ? "Se citește…" : "AI extrage"}</button>}
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
  const rows = useMemo(() => items.filter((i) => i.category === cat && !/\bTEST\b/i.test(String(i.brand_model || "")) && (!q || i.brand_model?.toLowerCase().includes(q.toLowerCase()))), [items, cat, q]);

  const save = async () => {
    if (!form.brand_model) return toast.error("Completează marca și modelul");
    const { id, ...rest } = form;
    if (id) await api.put(`/data/catalog/${id}`, rest); else await api.post("/data/catalog", { ...rest, category: cat });
    toast.success("Salvat"); setForm(null); load();
  };
  const remove = async (id) => { if (!window.confirm("Ștergi modelul din catalog?")) return; await api.delete(`/data/catalog/${id}`); load(); };

  const [importingOfficial, setImportingOfficial] = useState(false);
  const importOfficialDocuments = async () => {
    const jobs = items.flatMap((item) => ["datasheet", "conformity"]
      .filter((kind) => !item[kind] && (item[`${kind}_source_url`] || item[`${kind}_url`]))
      .map((kind) => ({ item, kind, url: item[`${kind}_source_url`] || item[`${kind}_url`] })));
    if (!jobs.length) return toast.info("Nu există PDF-uri oficiale noi de preluat; poți adăuga linkuri HTTPS în catalog.");
    setImportingOfficial(true);
    let imported = 0;
    const failed = [];
    try {
      for (const job of jobs) {
        try {
          await api.post(`/catalog/${job.item.id}/import-document`, { kind: job.kind, url: job.url });
          imported += 1;
        } catch (e) {
          failed.push(`${job.item.brand_model}: ${e.response?.data?.detail || "sursa nu a returnat un PDF valid"}`);
        }
      }
      await load();
      if (failed.length) {
        toast.warning(`Preluate ${imported} PDF-uri; ${failed.length} nu au putut fi importate. Verifică linkurile oficiale.`);
        console.warn("Importuri oficiale nereușite:", failed);
      } else {
        toast.success(`Preluate ${imported} PDF-uri oficiale în catalog`);
      }
    } finally { setImportingOfficial(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Bibliotecă echipamente" title="Catalog echipamente"
        sub="Modele cu date electrice, fișe tehnice și declarații de conformitate, reutilizate în configurarea CEF și în dosarele clienților."
        action={<div className="flex flex-wrap gap-2">
          <Btn variant="secondary" onClick={importOfficialDocuments} disabled={importingOfficial} data-testid="catalog-import-official-btn">
            <Upload size={14} /> {importingOfficial ? "Se preiau PDF-urile…" : "Preia PDF-urile oficiale"}
          </Btn>
          <a href="https://delgaz.ro/getattachment/f005023f-8d6f-4065-b6f5-cee47673593e/Lista-invertoare-conforme.xlsx" target="_blank" rel="noopener noreferrer" data-testid="catalog-delgaz-approved-inverters" className="inline-flex min-h-10 items-center justify-center rounded-lg border px-4 text-sm font-semibold" style={{ borderColor: "var(--line)", color: "var(--ink)" }} title="Lista oficială Delgaz Grid cu invertoare conforme">Listă invertoare Delgaz ↗</a>
          <Btn onClick={() => setForm(form ? null : { category: cat })} data-testid="catalog-add-btn">{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> Model nou</>}</Btn>
        </div>} />
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
        <div className="space-y-3" data-testid="catalog-cards">
          {rows.map((i) => (
            <article key={i.id} className="rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#fff" }} data-testid={`catalog-row-${i.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold break-words">{i.brand_model}</h3>
                  {i.notes && <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{i.notes}</p>}
                  <p className="mt-2 text-sm font-medium">{spec(i)}</p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button onClick={() => setForm({ ...i })} className="rounded-lg border p-2 hover:bg-[#eef4ff]" aria-label={`Editează ${i.brand_model}`} data-testid={`catalog-edit-${i.id}`}><Pencil size={15} style={{ color: "var(--blue)" }} /></button>
                  <button onClick={() => remove(i.id)} className="rounded-lg border p-2 hover:bg-[#fff0f0]" aria-label={`Șterge ${i.brand_model}`} data-testid={`catalog-delete-${i.id}`}><Trash2 size={15} style={{ color: "#b33333" }} /></button>
                </div>
              </div>
              <div className="mt-4 grid gap-3">
                <div className="min-w-0">
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Fișă tehnică</p>
                  <DocSlot item={i} k="datasheet" label="Fișă tehnică" onUploaded={load} />
                </div>
                <div className="min-w-0">
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Conformitate</p>
                  <DocSlot item={i} k="conformity" label="Certificat / declarație de conformitate" onUploaded={load} />
                </div>
              </div>
            </article>
          ))}
          {!rows.length && <p className="rounded-xl border p-6 text-center text-sm" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>Nu există modele în această categorie.</p>}
        </div>
      </div>
    </div>
  );
}
