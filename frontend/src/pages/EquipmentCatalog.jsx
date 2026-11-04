import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, openAuthenticatedFile } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { F, Check } from "@/components/cef/F";
import { Plus, Pencil, Trash2, Upload, FileText, X, Sparkles } from "lucide-react";
import { toast } from "sonner";

const CATS = ["Invertor", "Panou", "Baterie", "Smart meter", "Gateway", "Optimizator"];
const hasStoredDocument = (item, kind) => Boolean(item?.[kind]?.storage_path) && item?.[kind]?.available !== false;
const isCompositeEquipmentName = (name) => /\b(?:kit|bundle|pachet)\b/i.test(String(name || "")) || (/(?:invertor|inverter)/i.test(String(name || "")) && /(?:baterie|battery|\b\d+(?:[.,]\d+)?\s*kwh\b)/i.test(String(name || "")));
const FIELDS = {
  Invertor: [["type", "Tip", ["Hibrid", "On-grid", "Invertor de baterie (AC)"]], ["phases", "Faze", ["Trifazat", "Monofazat"]], ["p_nom_kw", "Pn (kW)"], ["p_max_kw", "Pmax (kW)"], ["red_limit_mode", "Limitare putere în RED", ["Nu este declarată", "Limitare putere evacuată", "Zero export"]],
    ["vdc_max", "Udc max (V)"], ["mppt_min", "MPPT min (V)"], ["mppt_max", "MPPT max (V)"], ["mppt_count", "Nr. MPPT"], ["imax_mppt", "Imax / MPPT (A)"], ["isc_max_mppt", "Isc max admisibil / MPPT (A)"], ["battery_voltage", "Tensiune baterie compatibilă", null, "text"], ["bat_i_max", "Curent max baterie (A)"]],
  Panou: [["w", "Putere (W)"], ["voc", "Voc (V)"], ["vmp", "Vmp (V)"], ["isc", "Isc (A)"], ["imp", "Imp (A)"], ["coef_voc", "Coef. Voc (%/°C)"], ["coef_vmp", "Coef. Vmp (%/°C)"], ["temp_noct", "NOCT (°C)"], ["temp_pmax", "Coef. Pmax (%/°C)"]],
  Baterie: [["kwh", "kWh / modul"], ["ah", "Ah"], ["voltage", "Tensiune (V)"], ["tech", "Tehnologie", ["LV", "HV"]], ["coupling", "Cuplare", ["DC", "AC"]], ["i_max", "Curent max descărcare (A)"], ["max_fuse_a", "Siguranță maximă admisă (A)"], ["breaker_a", "Întrerupător DC: curent nominal (A)"], ["breaker_voltage_dc", "Întrerupător DC: tensiune nominală (Vdc)"], ["breaker_poles", "Întrerupător DC: poli"], ["breaker_icu_ka", "Întrerupător DC: capacitate de rupere (kA)"], ["breaker_source_url", "Sursă pentru protecția DC", null, "url"]],
  "Smart meter": [["phases", "Faze", ["Trifazat", "Monofazat"]], ["current_max_a", "Curent nominal/max (A)"], ["voltage_nominal_v", "Tensiune nominală", null, "text"], ["frequency_hz", "Frecvență", null, "text"], ["protocol", "Protocol comunicație", null, "text"], ["wiring", "Configurație rețea", null, "text"], ["accuracy_class", "Clasă precizie", null, "text"]],
  Gateway: [["compatible_inverters", "Invertoare compatibile", null, "text"], ["protocol", "Protocol comunicație", null, "text"], ["interfaces", "Interfețe (Wi-Fi/Ethernet/RS485)", null, "text"], ["max_devices", "Număr maxim de dispozitive"], ["monitoring_platform", "Platformă de monitorizare", null, "text"]],
  Optimizator: [["compatible_inverters", "Invertoare compatibile", null, "text"], ["p_max_w", "Putere maximă modul (W)"], ["vdc_max", "Tensiune maximă intrare (V)"], ["imax_mppt", "Curent maxim intrare (A)"], ["model_scope", "Domeniu de utilizare (modul/string)", null, "text"]],
};
const spec = (i) => i.category === "Invertor" ? `${i.p_nom_kw ?? "—"} kW · ${i.phases || ""} · ${i.type || ""}` : i.category === "Panou" ? `${i.w ?? "—"} W · Voc ${i.voc ?? "—"} V` : i.category === "Baterie" ? `${i.kwh ?? "—"} kWh · ${i.ah || "—"} Ah · ${i.voltage ?? "—"} V · protecție DC ${i.breaker_a ?? "—"} A / ${i.breaker_voltage_dc ?? "—"} V` : i.category === "Smart meter" ? [i.phases, i.current_max_a ? i.current_max_a + " A max" : null, i.voltage_nominal_v, i.frequency_hz, i.protocol, i.wiring, i.accuracy_class].filter(Boolean).join(" · ") : i.category === "Gateway" ? [i.compatible_inverters, i.protocol, i.interfaces, i.max_devices ? `${i.max_devices} dispozitive` : null, i.monitoring_platform].filter(Boolean).join(" · ") : [i.compatible_inverters, i.p_max_w ? `${i.p_max_w} W` : null, i.vdc_max ? `${i.vdc_max} V max` : null, i.imax_mppt ? `${i.imax_mppt} A max` : null, i.model_scope].filter(Boolean).join(" · ");

function DocSlot({ item, k, label, onUploaded }) {
  const ref = useRef();
  const [sourceUrl, setSourceUrl] = useState(() => item[`${k}_source_url`] || item[`${k}_url`] || "");
  const officialUrl = item[`${k}_url`] || item[`${k}_source_url`] || "";
  const [importing, setImporting] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [feedbackUrl, setFeedbackUrl] = useState("");
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const f = item[k];
  const submitFeedback = async () => {
    if (!feedbackUrl.trim() && !feedbackNote.trim()) return toast.info("Adaugă un link oficial sau o observație.");
    setFeedbackBusy(true);
    try {
      await api.post(`/catalog/${item.id}/document-feedback`, {
        kind: k, suggested_url: feedbackUrl.trim(), note: feedbackNote.trim(),
      });
      toast.success("Propunerea a fost trimisă în lista de verificare a catalogului.");
      setFeedbackUrl(""); setFeedbackNote("");
      onUploaded();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Propunerea nu a putut fi trimisă.");
    } finally {
      setFeedbackBusy(false);
    }
  };
  const importUrl = async () => {
    setImporting(true);
    try {
      await api.post(`/catalog/${item.id}/import-document`, { kind: k, url: sourceUrl });
      toast.success(`${label} preluată de la sursa oficială`);
      setSourceUrl("");
      if (k === "datasheet") await runExtract({ silent: true });
      else onUploaded();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Importul documentului a eșuat");
    } finally {
      setImporting(false);
    }
  };
  const runExtract = async ({ silent = false } = {}) => {
    setExtracting(true);
    try {
      const { data } = await api.post(`/ai/catalog/${item.id}/extract`);
      const count = Object.keys(data.filled || {}).length;
      const skipped = (data.skipped_existing || []).length;
      const source = data.engine === "local_text" ? "local din textul PDF" : "cu AI";
      const message = count
        ? `${count} valori extrase ${source}; verifică-le înainte de folosire`
        : skipped
          ? `${skipped} valori existente au fost păstrate`
          : (data.message || "Nu au fost găsite valori noi de completat");
      if (silent) {
        if (count) toast.success(message);
        else toast.info(message);
      } else {
        toast.success(message);
      }
      onUploaded();
      return true;
    } catch (e) {
      const detail = e.response?.data?.detail || "Extragerea automată nu a reușit";
      if (silent) toast.warning(`Fișa a fost salvată, dar nu s-au putut extrage date: ${detail}`);
      else toast.error(detail);
      return false;
    } finally {
      setExtracting(false);
    }
  };
  const extract = async () => runExtract();
  const up = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      await api.put(`/data/catalog/${item.id}`, { [k]: data });
      toast.success(`${label} încărcată`);
      if (k === "datasheet" && (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"))) {
        await runExtract({ silent: true });
      } else {
        onUploaded();
      }
    } catch { toast.error("Eroare la încărcare"); } finally { ref.current.value = ""; }
  };
  return (
    <div className="w-full min-w-0">
      <span className="flex w-full min-w-0 flex-wrap items-center gap-2">
      <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={up} data-testid={`upload-${k}-${item.id}`} />
      {hasStoredDocument(item, k) ? <button type="button" onClick={() => openAuthenticatedFile(`/files/${f.storage_path}`)} className="inline-flex items-center gap-1 text-[12px] font-bold text-left" style={{ color: "var(--blue)" }} data-testid={`open-${k}-${item.id}`} title={f.source_url || "Document încărcat"}><FileText size={13} /> {label} atașată</button>
        : <span className="text-[12px]" style={{ color: "#b9770e" }}>{f?.available === false ? `${label} indisponibilă — reîncarcă PDF-ul` : f ? `${label} nepreluată` : `${label} lipsă`}</span>}
      {officialUrl && <a href={officialUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] underline" title="Deschide documentul de la producător">Sursă oficială ↗</a>}
      <button onClick={() => ref.current.click()} className="p-1 rounded hover:bg-[#eef4ff]" title={`Încarcă ${label}`} data-testid={`btn-upload-${k}-${item.id}`}><Upload size={13} style={{ color: "var(--blue)" }} /></button>
      <input className="den-input text-[11px] py-1 w-full sm:w-[220px] min-w-0" type="url" placeholder="Link PDF oficial HTTPS" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} aria-label={`Link oficial ${label}`} />
      <button onClick={importUrl} disabled={importing || !sourceUrl} className="text-[11px] font-bold px-2 py-1 rounded border disabled:opacity-50" title="Preia PDF de pe site-ul oficial" data-testid={`import-url-${k}-${item.id}`}>{importing ? "Se preia…" : "Importă PDF"}</button>
      {k === "datasheet" && f && <button onClick={extract} disabled={extracting} className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded border disabled:opacity-50" title="Extrage numai specificațiile care apar în fișa PDF" data-testid={`ai-extract-${item.id}`}><Sparkles size={12} /> {extracting ? "Se citește…" : "Extrage specificații"}</button>}
      </span>
      <details className="mt-2 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "#f8fafc" }} data-testid={`document-feedback-${k}-${item.id}`}>
        <summary className="cursor-pointer text-[11px] font-semibold underline" data-testid={`report-document-${k}-${item.id}`}>Semnalează document lipsă sau incorect</summary>
        <div className="mt-2 space-y-2">
          <p className="text-xs font-semibold">Propune un link oficial și/sau descrie problema. Propunerea intră la verificare înainte de import.</p>
          <input className="den-input w-full text-xs" type="url" placeholder="Link HTTPS către documentul corect (opțional)" value={feedbackUrl} onChange={(e) => setFeedbackUrl(e.target.value)} aria-label={`Link propus pentru ${label}`} data-testid={`feedback-url-${k}-${item.id}`} />
          <textarea className="den-input w-full text-xs" rows={2} maxLength={1000} placeholder="Ce lipsește sau ce trebuie corectat?" value={feedbackNote} onChange={(e) => setFeedbackNote(e.target.value)} aria-label={`Observație despre ${label}`} data-testid={`feedback-note-${k}-${item.id}`} />
          <button type="button" onClick={submitFeedback} disabled={feedbackBusy || (!feedbackUrl.trim() && !feedbackNote.trim())} className="rounded-lg border px-3 py-1.5 text-xs font-bold disabled:opacity-50" style={{ borderColor: "var(--line)" }} data-testid={`submit-feedback-${k}-${item.id}`}>{feedbackBusy ? "Se trimite…" : "Trimite spre verificare"}</button>
        </div>
      </details>
    </div>
  );
}

export default function EquipmentCatalog() {
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const initialSearch = new URLSearchParams(location.search);
  const initialCategory = initialSearch.get("category");
  const [cat, setCat] = useState(CATS.includes(initialCategory) ? initialCategory : "Invertor");
  const [q, setQ] = useState(initialSearch.get("q") || "");
  const [phaseFilter, setPhaseFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [minValue, setMinValue] = useState("");
  const [maxValue, setMaxValue] = useState("");
  const [completeDocsOnly, setCompleteDocsOnly] = useState(false);
  const [showCompositeProducts, setShowCompositeProducts] = useState(false);
  const [form, setForm] = useState(null);
  const [supplierResults, setSupplierResults] = useState([]);
  const [supplierLoading, setSupplierLoading] = useState(false);
  const [supplierNextOffset, setSupplierNextOffset] = useState(0);
  const [supplierHasMore, setSupplierHasMore] = useState(false);
  const [supplierBrowseAll, setSupplierBrowseAll] = useState(false);
  const [supplierImporting, setSupplierImporting] = useState("");
  const [supplierSelected, setSupplierSelected] = useState(() => new Set());
  const [supplierBulkBusy, setSupplierBulkBusy] = useState(false);
  const [supplierBulkProgress, setSupplierBulkProgress] = useState("");
  const [feedbacks, setFeedbacks] = useState([]);
  const [feedbackUpdating, setFeedbackUpdating] = useState("");
  const load = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const { data } = await api.get("/data/catalog");
      setItems(Array.isArray(data) ? data : []);
      try {
        const feedbackResponse = await api.get("/catalog/document-feedback");
        setFeedbacks(Array.isArray(feedbackResponse.data) ? feedbackResponse.data : []);
      } catch {
        setFeedbacks([]);
      }
    } catch (e) {
      setLoadError(e.response?.data?.detail || "Catalogul nu s-a putut încărca. Verifică conexiunea și încearcă din nou.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const nextCategory = params.get("category");
    if (params.has("q")) setQ(params.get("q") || "");
    if (CATS.includes(nextCategory)) setCat(nextCategory);
  }, [location.search]);
  useEffect(() => {
    setSupplierResults([]);
    setSupplierSelected(new Set());
    setSupplierHasMore(false);
  }, [cat]);
  const rows = useMemo(() => items.filter((i) => {
    if (i.category !== cat || /\bTEST\b/i.test(String(i.brand_model || ""))) return false;
    if (!showCompositeProducts && isCompositeEquipmentName(i.brand_model)) return false;
    if (q && !String(i.brand_model || "").toLocaleLowerCase("ro-RO").includes(q.toLocaleLowerCase("ro-RO"))) return false;
    if (phaseFilter && String(i.phases || "").toLocaleLowerCase("ro-RO") !== phaseFilter.toLocaleLowerCase("ro-RO")) return false;
    if (typeFilter && String(i.type || "").toLocaleLowerCase("ro-RO") !== typeFilter.toLocaleLowerCase("ro-RO")) return false;
    const measure = Number(cat === "Invertor" ? i.p_nom_kw : cat === "Panou" ? i.w : cat === "Baterie" ? i.kwh : cat === "Smart meter" ? i.current_max_a : cat === "Gateway" ? i.max_devices : i.p_max_w);
    if (minValue !== "" && (!Number.isFinite(measure) || measure < Number(minValue))) return false;
    if (maxValue !== "" && (!Number.isFinite(measure) || measure > Number(maxValue))) return false;
    const hasDatasheet = hasStoredDocument(i, "datasheet");
    const hasConformity = hasStoredDocument(i, "conformity");
    if (completeDocsOnly && !(hasDatasheet && hasConformity)) return false;
    return true;
  }), [items, cat, q, phaseFilter, typeFilter, minValue, maxValue, completeDocsOnly, showCompositeProducts]);
  const compositeCount = items.filter((i) => i.category === cat && isCompositeEquipmentName(i.brand_model)).length;
  const completeDocsCount = items.filter((i) => i.category === cat
    && !/\bTEST\b/i.test(String(i.brand_model || ""))
    && hasStoredDocument(i, "datasheet")
    && hasStoredDocument(i, "conformity")).length;
  const categoryCounts = useMemo(() => Object.fromEntries(CATS.map((category) => {
    const models = items.filter((item) => item.category === category && !/\bTEST\b/i.test(String(item.brand_model || "")));
    return [category, { total: models.length, complete: models.filter((item) => hasStoredDocument(item, "datasheet") && hasStoredDocument(item, "conformity")).length }];
  })), [items]);
  const measureLabel = cat === "Invertor" ? "putere nominală (kW)" : cat === "Panou" ? "putere panou (W)" : cat === "Baterie" ? "capacitate (kWh)" : cat === "Smart meter" ? "curent max. (A)" : cat === "Gateway" ? "dispozitive" : "putere modul (W)";
  const clearFilters = () => { setPhaseFilter(""); setTypeFilter(""); setMinValue(""); setMaxValue(""); setCompleteDocsOnly(false); setQ(""); };

  const save = async () => {
    if (!form.brand_model) return toast.error("Completează marca și modelul");
    const { id, ...rest } = form;
    if (id) await api.put(`/data/catalog/${id}`, rest); else await api.post("/data/catalog", { ...rest, category: cat });
    toast.success("Salvat"); setForm(null); load();
  };
  const remove = async (id) => { if (!window.confirm("Ștergi modelul din catalog?")) return; await api.delete(`/data/catalog/${id}`); load(); };

  const searchSuppliers = async (append = false, browseAll = false) => {
    const browse = append ? supplierBrowseAll : browseAll;
    if (!browse && q.trim().length < 2) return toast.info("Scrie cel puțin două caractere pentru căutarea la furnizori.");
    const offset = append ? supplierNextOffset : 0;
    if (!append) setSupplierBrowseAll(browse);
    setSupplierLoading(true);
    try {
      const { data } = await api.get("/catalog/supplier-search", {
        params: { q: browse ? "__browse_catalog__" : q.trim(), category: cat, offset, limit: 24 }, timeout: 60000,
      });
      const products = Array.isArray(data.products) ? data.products : [];
      setSupplierResults((previous) => {
        if (!append) return products;
        const seen = new Set(previous.map((product) => product.product_url));
        return [...previous, ...products.filter((product) => !seen.has(product.product_url))];
      });
      setSupplierNextOffset(Number(data.next_offset) || offset);
      setSupplierHasMore(Boolean(data.has_more));
      if (!products.length && !append && !data.has_more) toast.info(data.message || "Nu s-au găsit produse.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Căutarea la furnizori nu este disponibilă acum.");
    } finally { setSupplierLoading(false); }
  };

  const importSupplierProduct = async (product) => {
    const key = product.product_url;
    setSupplierImporting(key);
    try {
      const { data } = await api.post("/catalog/supplier-import", {
        supplier: product.supplier, category: product.category, product_url: product.product_url,
      });
      await load();
      toast.success(data.existing
        ? "Modelul este deja în catalog."
        : "Model adăugat cu datele tehnice publicate și documentele PDF disponibile.");
      if (!product.datasheet_url && !product.conformity_url) {
        toast.warning("Furnizorul nu a expus linkuri directe către fișă sau certificat; poți adăuga documentele ulterior.");
      }
      // Extract explicit values from an imported datasheet without delaying catalog access.
      if (!data.existing && data.item?.id && data.item?.datasheet?.storage_path) {
        api.post(`/ai/catalog/${data.item.id}/extract`)
          .then(({ data: result }) => {
            const count = Object.keys(result?.filled || {}).length;
            if (count) toast.success(`${count} parametri tehnici extrași automat din fișa modelului.`);
            load();
          })
          .catch(() => toast.info("Fișa a fost salvată. Extragerea automată nu este disponibilă acum; modelul rămâne în catalog și poate fi completat ulterior."));
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Produsul nu a putut fi adăugat în catalog.");
    } finally { setSupplierImporting(""); }
  };

  const toggleSupplierSelection = (product) => {
    if (!product.datasheet_url || !product.conformity_url) return;
    setSupplierSelected((previous) => {
      const next = new Set(previous);
      if (next.has(product.product_url)) next.delete(product.product_url);
      else next.add(product.product_url);
      return next;
    });
  };

  const selectSupplierProductsWithDocuments = () => {
    setSupplierSelected(new Set(supplierResults
      .filter((product) => product.datasheet_url && product.conformity_url)
      .map((product) => product.product_url)));
  };

  const importSelectedSupplierProducts = async () => {
    const selected = supplierResults.filter((product) => supplierSelected.has(product.product_url)
      && product.datasheet_url && product.conformity_url);
    if (!selected.length) return toast.info("Selectează modele pentru care furnizorul oferă ambele PDF-uri.");
    setSupplierBulkBusy(true);
    let imported = 0;
    let existing = 0;
    let extractionFailed = 0;
    const failedProducts = [];
    try {
      for (let index = 0; index < selected.length; index += 1) {
        const product = selected[index];
        setSupplierBulkProgress(`Se verifică modelul ${index + 1} din ${selected.length}: ${product.brand_model}`);
        try {
          const { data } = await api.post("/catalog/supplier-import", {
            supplier: product.supplier, category: product.category, product_url: product.product_url,
          }, { timeout: 60000 });
          if (data.existing) {
            existing += 1;
            continue;
          }
          imported += 1;
          if (data.item?.id && data.item?.datasheet?.storage_path) {
            setSupplierBulkProgress(`Se extrag specificațiile ${index + 1} din ${selected.length}: ${product.brand_model}`);
            try { await api.post(`/ai/catalog/${data.item.id}/extract`, {}, { timeout: 90000 }); }
            catch { extractionFailed += 1; }
          }
        } catch {
          failedProducts.push(product);
        }
      }
      await load();
      setSupplierSelected(new Set(failedProducts.map((product) => product.product_url)));
      if (failedProducts.length || extractionFailed) {
        toast.warning(`${imported} modele noi, ${existing} deja existente; ${failedProducts.length} importuri eșuate${extractionFailed ? `, ${extractionFailed} extrageri AI nereușite` : ""}.`);
      } else {
        toast.success(`${imported} modele adăugate cu PDF-urile furnizorului; ${existing} erau deja în catalog.`);
      }
    } finally {
      setSupplierBulkBusy(false);
      setSupplierBulkProgress("");
    }
  };

  const reviewFeedback = async (feedback, status = "reviewed") => {
    setFeedbackUpdating(feedback.id);
    try {
      await api.patch(`/catalog/document-feedback/${feedback.id}`, { status });
      toast.success(status === "dismissed" ? "Propunerea a fost închisă." : "Propunerea a fost marcată ca verificată.");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Propunerea nu a putut fi actualizată.");
    } finally {
      setFeedbackUpdating("");
    }
  };

  const importFeedback = async (feedback) => {
    if (!feedback.suggested_url) return reviewFeedback(feedback, "reviewed");
    setFeedbackUpdating(feedback.id);
    try {
      await api.post(`/catalog/${feedback.item_id}/import-document`, { kind: feedback.kind, url: feedback.suggested_url });
      await api.patch(`/catalog/document-feedback/${feedback.id}`, { status: "accepted" });
      toast.success("Documentul propus a fost importat și asociat modelului.");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Documentul nu a putut fi importat. Verifică să fie HTTPS și de la o sursă permisă.");
    } finally {
      setFeedbackUpdating("");
    }
  };

  const [importingOfficial, setImportingOfficial] = useState(false);
  const [officialImportProgress, setOfficialImportProgress] = useState("");
  const importOfficialDocuments = async () => {
    const jobs = items.flatMap((item) => ["datasheet", "conformity"]
      .filter((kind) => !hasStoredDocument(item, kind) && (item[`${kind}_source_url`] || item[`${kind}_url`]))
      .map((kind) => ({ item, kind, url: item[`${kind}_source_url`] || item[`${kind}_url`] })));
    if (!jobs.length) return toast.info("Nu există PDF-uri oficiale noi de preluat; poți adăuga linkuri HTTPS în catalog.");
    setImportingOfficial(true);
    setOfficialImportProgress(`0 / ${jobs.length} documente`);
    let imported = 0;
    let extractedModels = 0;
    let extractionFailed = 0;
    let completed = 0;
    let cursor = 0;
    const failed = [];
    const worker = async () => {
      while (cursor < jobs.length) {
        const job = jobs[cursor++];
        try {
          await api.post(`/catalog/${job.item.id}/import-document`, { kind: job.kind, url: job.url }, { timeout: 90000 });
          imported += 1;
          if (job.kind === "datasheet") {
            try {
              const { data } = await api.post(`/ai/catalog/${job.item.id}/extract`, {}, { timeout: 90000 });
              if (Object.keys(data?.filled || {}).length) extractedModels += 1;
            } catch {
              extractionFailed += 1;
            }
          }
        } catch (e) {
          failed.push(`${job.item.brand_model}: ${e.response?.data?.detail || "sursa nu a returnat un PDF valid"}`);
        } finally {
          completed += 1;
          setOfficialImportProgress(`${completed} / ${jobs.length} documente`);
        }
      }
    };
    try {
      await Promise.all(Array.from({ length: Math.min(3, jobs.length) }, () => worker()));
      await load();
      const summary = `Preluate ${imported} PDF-uri oficiale${extractedModels ? `; extrase date din ${extractedModels} fișe tehnice` : ""}.`;
      if (failed.length || extractionFailed) {
        toast.warning(`${summary} ${failed.length ? `${failed.length} documente au eșuat.` : ""}${extractionFailed ? ` Extragerea nu a reușit pentru ${extractionFailed} fișe.` : ""}`);
        if (failed.length) console.warn("Importuri oficiale nereușite:", failed);
      } else {
        toast.success(summary);
      }
    } finally {
      setImportingOfficial(false);
      setOfficialImportProgress("");
    }
  };

  return (
    <div>
      <PageHeader eyebrow="Bibliotecă echipamente" title="Catalog echipamente"
        sub="Modele cu date electrice, fișe tehnice și declarații de conformitate, reutilizate în configurarea CEF și în dosarele clienților."
        action={<div className="flex flex-wrap gap-2">
          <Btn variant="secondary" onClick={importOfficialDocuments} disabled={importingOfficial} data-testid="catalog-import-official-btn">
            <Upload size={14} /> {importingOfficial ? (officialImportProgress || "Se preiau PDF-urile…") : "Preia PDF-urile și extrage datele"}
          </Btn>
          <a href="https://delgaz.ro/getattachment/f005023f-8d6f-4065-b6f5-cee47673593e/Lista-invertoare-conforme.xlsx" target="_blank" rel="noopener noreferrer" data-testid="catalog-delgaz-approved-inverters" className="inline-flex min-h-10 items-center justify-center rounded-lg border px-4 text-sm font-semibold" style={{ borderColor: "var(--line)", color: "var(--ink)" }} title="Lista oficială Delgaz Grid cu invertoare conforme">Listă invertoare Delgaz ↗</a>
          <Btn onClick={() => setForm(form ? null : { category: cat })} data-testid="catalog-add-btn">{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> Model nou</>}</Btn>
        </div>} />
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Categorii echipamente">
        {CATS.map((c) => <button key={c} onClick={() => { setCat(c); setForm(null); setPhaseFilter(""); setTypeFilter(""); setMinValue(""); setMaxValue(""); setCompleteDocsOnly(false); }} data-testid={`catalog-tab-${c}`}
          role="tab" aria-selected={c === cat} className="shrink-0 rounded-full border px-3 py-2 text-xs font-bold transition-colors" style={c === cat ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>
          {c}<span className="ml-2 text-[10px] font-medium opacity-75">{categoryCounts[c]?.total || 0}</span></button>)}
      </div>
      {compositeCount > 0 && <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm" data-testid="catalog-composite-notice"><span>{compositeCount} listări par a combina invertorul și bateria într-un singur pachet. Dosarele folosesc echipamente individuale din fișe tehnice.</span><button type="button" className="font-semibold underline" onClick={() => setShowCompositeProducts((value) => !value)} data-testid="catalog-toggle-composite">{showCompositeProducts ? "Ascunde pachetele" : "Arată pachetele pentru corectare"}</button></div>}
      <div className="den-panel mb-3 flex flex-col gap-3 p-3 sm:flex-row sm:items-center" data-testid="catalog-unified-search">
        <input className="den-input min-w-0 flex-1" placeholder={`Caută ${cat.toLocaleLowerCase("ro-RO")} după marcă sau model…`} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Caută în catalog și la furnizori" data-testid="catalog-db-search" />
        <Btn onClick={() => searchSuppliers()} disabled={supplierLoading || q.trim().length < 2} data-testid="supplier-search-btn">
          {supplierLoading && !supplierBrowseAll ? "Se caută…" : "Caută la furnizori"}
        </Btn>
        <Btn variant="secondary" onClick={() => searchSuppliers(false, true)} disabled={supplierLoading} data-testid="supplier-browse-btn">
          {supplierLoading && supplierBrowseAll ? "Se încarcă…" : "Răsfoiește modelele"}
        </Btn>
        <span className="text-[11px] sm:max-w-48" style={{ color: "var(--muted)" }}>{rows.length} în catalog · {completeDocsCount} cu ambele PDF-uri</span>
      </div>
      {form ? (
        <div className="den-panel mb-6" data-testid="catalog-form">
          <h2 className="text-lg font-bold mb-4">{form.id ? "Editează modelul" : `Model nou — ${cat}`}</h2>
          <div className="grid sm:grid-cols-3 gap-3">
            <F label="Marcă și model *" value={form.brand_model} onChange={(v) => setForm({ ...form, brand_model: v })} testid="cat-field-brand_model" className="sm:col-span-2" />
            {FIELDS[form.category || cat].map(([k, l, opts, t]) => <F key={k} label={l} value={form[k]} options={opts || undefined} type={opts ? undefined : (t || "number")} onChange={(v) => setForm({ ...form, [k]: v })} testid={`cat-field-${k}`} />)}
            {(form.category || cat) === "Baterie" && <Check label="Întrerupătorul DC este integrat în baterie (conform fișei)" value={!!form.breaker_integrated} onChange={(v) => setForm({ ...form, breaker_integrated: v })} testid="cat-field-breaker-integrated" />}
            <F label="Observații" value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} testid="cat-field-notes" className="sm:col-span-3" />
          </div>
          <div className="flex gap-2 mt-5"><Btn onClick={save} data-testid="catalog-save-btn">Salvează</Btn><Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn></div>
          {!form.id && <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>După salvare poți încărca fișa tehnică și declarația de conformitate din listă.</p>}
        </div>
      ) : null}
      {feedbacks.length > 0 && <section className="den-panel mb-4" aria-label="Propuneri de documente pentru catalog" data-testid="catalog-feedback-queue">
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <div>
            <h2 className="font-bold">Verifică documentele propuse ({feedbacks.length})</h2>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Importul verifică din nou sursa și acceptă numai domeniile oficiale permise.</p>
          </div>
        </div>
        <div className="space-y-2">
          {feedbacks.map((feedback) => <article key={feedback.id} className="rounded-xl border p-3" style={{ borderColor: "var(--line)" }} data-testid={`catalog-feedback-${feedback.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-bold">{feedback.brand_model || "Model catalog"} <span className="font-normal">· {feedback.kind === "datasheet" ? "Fișă tehnică" : "Conformitate"}</span></p>
                {feedback.note && <p className="text-xs mt-1">{feedback.note}</p>}
                {feedback.suggested_url && <a href={feedback.suggested_url} target="_blank" rel="noopener noreferrer" className="text-xs underline break-all">Deschide documentul propus ↗</a>}
                <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Propus de {feedback.submitted_by || "utilizator"} · {feedback.category || ""}</p>
              </div>
              <div className="flex gap-2">
                {feedback.suggested_url && <button type="button" onClick={() => importFeedback(feedback)} disabled={feedbackUpdating === feedback.id} className="rounded-lg border px-3 py-1.5 text-xs font-bold disabled:opacity-50" style={{ borderColor: "var(--line)" }} data-testid={`feedback-import-${feedback.id}`}>{feedbackUpdating === feedback.id ? "Se verifică…" : "Verifică și importă"}</button>}
                <button type="button" onClick={() => reviewFeedback(feedback)} disabled={feedbackUpdating === feedback.id} className="rounded-lg border px-3 py-1.5 text-xs font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }} data-testid={`feedback-reviewed-${feedback.id}`}>Marchează verificat</button>
                <button type="button" onClick={() => reviewFeedback(feedback, "dismissed")} disabled={feedbackUpdating === feedback.id} className="px-2 py-1.5 text-xs underline disabled:opacity-50">Închide</button>
              </div>
            </div>
          </article>)}
        </div>
      </section>}
      <section className="den-panel mb-4 p-3" aria-label="Căutare la furnizori" data-testid="supplier-search-panel">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold">Modele de la furnizori</h2>
            <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Depozit Solar · SolarHev · SolarTech · Optim Solar. Prețul și stocul se verifică la comerciant.</p>
          </div>
          {supplierResults.length > 0 && <span className="text-[11px]" style={{ color: "var(--muted)" }}>{supplierResults.length} rezultate încărcate</span>}
        </div>
        {supplierResults.length > 0 && <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="supplier-bulk-import">
          <button type="button" onClick={selectSupplierProductsWithDocuments} disabled={supplierBulkBusy} className="rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }} data-testid="supplier-select-complete">Selectează modelele cu ambele PDF-uri</button>
          <button type="button" onClick={() => setSupplierSelected(new Set())} disabled={supplierBulkBusy || supplierSelected.size === 0} className="rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50" style={{ borderColor: "var(--line)" }}>Șterge selecția</button>
          <button type="button" onClick={importSelectedSupplierProducts} disabled={supplierBulkBusy || supplierSelected.size === 0} className="rounded-lg px-3 py-2 text-xs font-bold text-white disabled:opacity-50" style={{ background: "var(--blue)" }} data-testid="supplier-import-selected">{supplierBulkBusy ? "Se importă…" : `Importă ${supplierSelected.size} selectate în DNS`}</button>
          {supplierBulkProgress && <span role="status" className="w-full text-xs" style={{ color: "var(--muted)" }}>{supplierBulkProgress}</span>}
        </div>}
        {supplierResults.length > 0 && <div className="grid md:grid-cols-2 gap-3 mt-4">
          {supplierResults.map((product) => <article key={product.product_url} className="rounded-xl border p-3" style={{ borderColor: "var(--line)" }}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <label className="mb-2 flex items-center gap-2 text-[11px] font-semibold">
                  <input type="checkbox" checked={supplierSelected.has(product.product_url)} onChange={() => toggleSupplierSelection(product)} disabled={supplierBulkBusy || !product.datasheet_url || !product.conformity_url} aria-label={`Selectează ${product.brand_model} pentru import`} data-testid="supplier-product-select" />
                  {product.datasheet_url && product.conformity_url ? "Selectează pentru import multiplu" : "Importul multiplu cere ambele PDF-uri"}
                </label>
                <div className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--blue)" }}>{product.supplier}</div>
                <h3 className="font-bold text-sm mt-1">{product.brand_model}</h3>
                <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{[product.price_text, product.availability].filter(Boolean).join(" · ") || "Preț/stoc vezi la furnizor"}</p>
                <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>{Object.entries(product).filter(([key, value]) => value !== null && value !== undefined && ["p_nom_kw", "p_max_kw", "vdc_max", "mppt_min", "mppt_max", "mppt_count", "imax_mppt", "w", "voc", "coef_voc", "coef_vmp", "temp_pmax", "vmp", "isc", "imp", "kwh", "ah", "voltage", "i_max"].includes(key)).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Specificațiile tehnice nu sunt publicate structurat."}</p>
              </div>
              <a href={product.product_url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold whitespace-nowrap" style={{ color: "var(--blue)" }}>Produs ↗</a>
            </div>
            <div className="flex flex-wrap gap-2 mt-3 text-[11px]">
              {product.datasheet_url ? <a href={product.datasheet_url} target="_blank" rel="noopener noreferrer" className="underline">Fișă tehnică PDF ↗</a> : <span style={{ color: "var(--muted)" }}>Fișă tehnică: indisponibilă direct</span>}
              {product.conformity_url && <a href={product.conformity_url} target="_blank" rel="noopener noreferrer" className="underline">Conformitate PDF ↗</a>}
            </div>
            <button onClick={() => importSupplierProduct(product)} disabled={supplierBulkBusy || supplierImporting === product.product_url} className="mt-3 rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-50" style={{ borderColor: "var(--line)" }}>
              {supplierImporting === product.product_url ? "Se adaugă și se citesc documentele…" : "Adaugă modelul și documentele în DNS"}
            </button>
          </article>)}
        </div>}
        {supplierHasMore && <div className="mt-3 flex justify-center"><Btn variant="secondary" onClick={() => searchSuppliers(true)} disabled={supplierLoading} data-testid="supplier-search-more">{supplierLoading ? "Se încarcă…" : "Încarcă următoarele rezultate"}</Btn></div>}
      </section>
      <div className="den-panel">
        <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold">{cat} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({rows.length} din {categoryCounts[cat]?.total || 0})</span></h2>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{completeDocsCount} modele au fișa tehnică și declarația de conformitate PDF salvate în catalog. Linkurile producătorului rămân surse de preluare până când PDF-ul este atașat.</p>
          </div>
        </div>
        <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4" data-testid="catalog-filters">
          {(cat === "Invertor" || cat === "Smart meter") && <select className="den-input" value={phaseFilter} onChange={(e) => setPhaseFilter(e.target.value)} aria-label="Filtrează după faze" data-testid="catalog-filter-phases">
            <option value="">Monofazat și trifazat</option><option value="Monofazat">Monofazat</option><option value="Trifazat">Trifazat</option>
          </select>}
          {cat === "Invertor" && <select className="den-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Filtrează după tipul invertorului" data-testid="catalog-filter-type">
            <option value="">Toate tipurile</option><option value="Hibrid">Hibrid</option><option value="On-grid">On-grid</option><option value="Invertor de baterie (AC)">Invertor de baterie (AC)</option>
          </select>}
          <div className="flex gap-2">
            <input className="den-input min-w-0" type="number" min="0" placeholder={`Min. ${measureLabel}`} value={minValue} onChange={(e) => setMinValue(e.target.value)} aria-label={`Valoare minimă: ${measureLabel}`} data-testid="catalog-filter-min" />
            <input className="den-input min-w-0" type="number" min="0" placeholder={`Max. ${measureLabel}`} value={maxValue} onChange={(e) => setMaxValue(e.target.value)} aria-label={`Valoare maximă: ${measureLabel}`} data-testid="catalog-filter-max" />
          </div>
          <label className="flex min-h-10 items-center gap-2 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }}>
            <input type="checkbox" checked={completeDocsOnly} onChange={(e) => setCompleteDocsOnly(e.target.checked)} data-testid="catalog-filter-complete-docs" />
            Doar modele cu PDF-urile atașate
          </label>
          {(phaseFilter || typeFilter || minValue || maxValue || completeDocsOnly || q) && <button type="button" onClick={clearFilters} className="text-xs font-semibold underline justify-self-start" data-testid="catalog-clear-filters">Șterge filtrele</button>}
        </div>
        <div className="space-y-3" data-testid="catalog-cards">
          {rows.map((i) => (
            <article key={i.id} className="rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#fff" }} data-testid={`catalog-row-${i.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold break-words">{i.brand_model}</h3>
                  {i.notes && <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{i.notes}</p>}
                  <p className="mt-2 text-sm font-medium">{spec(i)}</p>
                  {FIELDS[i.category]?.length > 0 && <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }} data-testid={`catalog-spec-coverage-${i.id}`}>
                    Date tehnice introduse: {FIELDS[i.category].filter(([key]) => i[key] !== null && i[key] !== undefined && String(i[key]).trim() !== "").length}/{FIELDS[i.category].length} câmpuri din catalog
                  </p>}
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
          {loading && <p className="rounded-xl border p-6 text-center text-sm" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>Se încarcă modelele din catalog…</p>}
          {!loading && loadError && <div className="rounded-xl border p-5 text-center" style={{ borderColor: "#f0c8c8", background: "#fff6f6" }} role="alert"><p className="text-sm mb-3" style={{ color: "#a33" }}>{loadError}</p><Btn variant="secondary" onClick={load} data-testid="catalog-retry-btn">Încearcă din nou</Btn></div>}
          {!loading && !loadError && !rows.length && <p className="rounded-xl border p-6 text-center text-sm" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>Nu există modele în această categorie.</p>}
        </div>
      </div>
    </div>
  );
}

