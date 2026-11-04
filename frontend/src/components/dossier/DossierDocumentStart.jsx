import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FileText, Plus, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";

const TYPES = [
  ["ci", "1. Carte de identitate", "Actul clientului; se extrag numele, CNP-ul și domiciliul."],
  ["factura", "2. Factură de energie", "Se extrag POD-ul, operatorul și adresa locului de consum."],
  ["cf", "3. Carte funciară", "Se extrag numărul CF și numărul cadastral."],
  ["altele", "4. Alte documente", "PDF, imagini, DOCX și XLSX pot fi citite și rezumate; DOC/XLS și alte formate se atașează pentru verificare manuală."],
];

const EMPTY = { client_name: "", kind: "", bank: "", iban: "", cnp: "", hq_address: "", address_same_as_ci: false, county: "", locality: "", address: "", postal_code: "", pod: "", nlc: "", operator: "", supplier: "", cf_nr: "", cadastral_nr: "", phone: "", email: "", id_series: "", id_number: "", request_type: "Racordare prosumator — fără spor de putere" };
const COUNTY_OPERATOR = {
  bihor: "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  "bistrita nasaud": "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  cluj: "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  maramures: "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  "satu mare": "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  salaj: "Distribuție Energie Electrică Romania Sucursala Transilvania Nord",
  alba: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  brasov: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  covasna: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  harghita: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  mures: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  sibiu: "Distribuție Energie Electrică Romania Sucursala Transilvania Sud",
  braila: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  buzau: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  dambovita: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  galati: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  prahova: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  vrancea: "Distribuție Energie Electrică Romania Sucursala Muntenia Nord",
  bacau: "Delgaz Grid S.A.",
  botosani: "Delgaz Grid S.A.",
  iasi: "Delgaz Grid S.A.",
  neamt: "Delgaz Grid S.A.",
  suceava: "Delgaz Grid S.A.",
  vaslui: "Delgaz Grid S.A.",
  arges: "Distribuție Energie Oltenia S.A.",
  dolj: "Distribuție Energie Oltenia S.A.",
  gorj: "Distribuție Energie Oltenia S.A.",
  mehedinti: "Distribuție Energie Oltenia S.A.",
  olt: "Distribuție Energie Oltenia S.A.",
  teleorman: "Distribuție Energie Oltenia S.A.",
  valcea: "Distribuție Energie Oltenia S.A.",
  arad: "Rețele Electrice Banat S.A.",
  "caras severin": "Rețele Electrice Banat S.A.",
  hunedoara: "Rețele Electrice Banat S.A.",
  timis: "Rețele Electrice Banat S.A.",
  calarasi: "Rețele Electrice Dobrogea S.A.",
  constanta: "Rețele Electrice Dobrogea S.A.",
  ialomita: "Rețele Electrice Dobrogea S.A.",
  tulcea: "Rețele Electrice Dobrogea S.A.",
  giurgiu: "Rețele Electrice Muntenia S.A.",
  ilfov: "Rețele Electrice Muntenia S.A.",
  bucuresti: "Rețele Electrice Muntenia S.A.",
};

const LOCATION_FIELDS = ["address", "county", "locality", "postal_code", "pod", "nlc", "operator", "supplier", "cf_nr", "cadastral_nr"];
function clientConsumptionSites(client) {
  const saved = Array.isArray(client?.consumption_sites)
    ? client.consumption_sites.filter((site) => site && typeof site === "object").map((site, index) => ({ ...site, id: String(site.id || ("saved-" + index)) }))
    : [];
  if (saved.length) return saved;
  if (["address", "pod", "locality", "county"].some((key) => String(client?.[key] || "").trim())) {
    return [{ id: "legacy", ...Object.fromEntries(LOCATION_FIELDS.map((key) => [key, client?.[key] || ""])) }];
  }
  return [];
}

const normalizeLocation = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z ]/g, " ").replace(/\s+/g, " ").trim().replace(/^(jud(?:etul)?|municipiul|mun) /, "");
function distributorSuggestion(pod, county) {
  const code = String(pod || "").replace(/\s+/g, "").toUpperCase();
  if (code.startsWith("RO001E")) return "Rețele Electrice Muntenia S.A.";
  if (code.startsWith("RO002E")) return "Rețele Electrice Dobrogea S.A.";
  if (code.startsWith("RO005E")) return "Rețele Electrice Banat S.A.";
  if (code.startsWith("EMO3")) return "Delgaz Grid S.A.";
  if (/^\d{26}$/.test(code)) return "Distribuție Energie Oltenia S.A.";
  const countyOperator = COUNTY_OPERATOR[normalizeLocation(county)] || "";
  if (/^5940\d{14}$/.test(code)) return countyOperator.startsWith("Distribuție Energie Electrică Romania") ? countyOperator : "DEER — sucursală de confirmat";
  return countyOperator;
}

// Some mobile document pickers report a blank or generic MIME type even when the
// filename is a supported PDF/image. Use the extension as a safe fallback.
const READABLE_EXTENSIONS = /\.(pdf|jpe?g|png|webp|heic|heif|docx|xlsx)$/i;

function putNonempty(base, next) {
  const out = { ...base };
  for (const [k, v] of Object.entries(next)) if (v !== null && v !== undefined && String(v).trim()) out[k] = String(v).trim();
  return out;
}

export function DossierDocumentStart({ onCreated, autoOpen = false }) {
  const [open, setOpen] = useState(Boolean(autoOpen));
  const [values, setValues] = useState(EMPTY);
  const [files, setFiles] = useState({ ci: [], factura: [], cf: [], altele: [] });
  const [notes, setNotes] = useState({});
  const [busy, setBusy] = useState("");
  const [step, setStep] = useState(0);
  const [clientSearch, setClientSearch] = useState("");
  const [clientMatches, setClientMatches] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [selectedSiteId, setSelectedSiteId] = useState("new");
  const [operatorManuallySet, setOperatorManuallySet] = useState(false);
  const [clientDetailsOpen, setClientDetailsOpen] = useState(false);
  const inputs = useRef({});

  useEffect(() => { if (autoOpen) setOpen(true); }, [autoOpen]);

  const selectExistingClient = async (result) => {
    try {
      setBusy("client");
      const { data: client } = await api.get(`/data/clients/${encodeURIComponent(result.id)}`);
      const sites = clientConsumptionSites(client);
      const firstSite = sites[0] || null;
      const selected = { ...client, title: client.name || result.title, detail: result.detail, consumption_sites: sites };
      setSelectedClient(selected); setSelectedSiteId(firstSite?.id || "new"); setClientSearch(""); setClientMatches([]);
      setValues((prev) => ({ ...EMPTY, ...prev, client_id: selected.id, client_name: selected.title || "", kind: selected.kind || "", bank: selected.bank || "", iban: selected.iban || "", cnp: selected.idcode || selected.cui || "", id_series: selected.id_series || "", id_number: selected.id_number || "", phone: selected.phone || "", email: selected.email || "", hq_address: selected.hq_address || "", ...Object.fromEntries(LOCATION_FIELDS.map((key) => [key, firstSite?.[key] || selected[key] || ""])), operator: firstSite?.operator || selected.operator || distributorSuggestion(firstSite?.pod || selected.pod, firstSite?.county || selected.county), address_same_as_ci: false }));
      setOperatorManuallySet(Boolean(selected.operator));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Nu am putut încărca datele clientului selectat.");
    } finally { setBusy(""); }
  };


  const selectConsumptionSite = (siteId) => {
    setSelectedSiteId(siteId);
    if (siteId === "new") {
      setOperatorManuallySet(false);
      setValues((prev) => ({ ...prev, ...Object.fromEntries(LOCATION_FIELDS.map((key) => [key, ""])), address_same_as_ci: false }));
      return;
    }
    const site = (selectedClient?.consumption_sites || []).find((item) => String(item.id) === String(siteId));
    if (!site) return;
    setOperatorManuallySet(Boolean(site.operator));
    setValues((prev) => ({ ...prev, ...Object.fromEntries(LOCATION_FIELDS.map((key) => [key, site[key] || ""])), address_same_as_ci: false }));
  };

  useEffect(() => {
    const term = clientSearch.trim();
    if (!open || step !== 0 || term.length < 2 || selectedClient) {
      setClientMatches([]);
      return undefined;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await api.get("/clients/search", { params: { q: term } });
        if (active) setClientMatches(Array.isArray(data.results) ? data.results : []);
      } catch {
        if (active) setClientMatches([]);
      }
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [clientSearch, open, selectedClient, step]);

  const extract = async (kind, selected) => {
    const list = Array.from(selected || []);
    if (!list.length) return;
    setBusy(kind);
    const mergedFiles = [...(files[kind] || [])];
    const initialCount = mergedFiles.length;
    let mergedValues = values;
    const summaries = [];
    const extractionWarnings = [];
    let failed = 0;
    let attachedWithoutRead = 0;
    let firstFailure = "";
    for (const file of list) {
      let attached = false;
      try {
        const officeExtractable = /\.(docx|xlsx)$/i.test(file.name);
        const mime = String(file.type || "").toLowerCase().split(";")[0].trim();
        const extensionExtractable = READABLE_EXTENSIONS.test(file.name || "");
        const extractable = mime === "application/pdf" || mime.startsWith("image/") || officeExtractable || extensionExtractable;
        if (kind === "altele" && !extractable) {
          const fd = new FormData(); fd.append("file", file);
          const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
          mergedFiles.push(data);
          summaries.push(`${file.name}: atașat; formatul nu are citire automată, necesită verificare manuală`);
          continue;
        }
        if (!extractable) throw new Error("Formatul nu este acceptat pentru citire automată.");
        const fd = new FormData(); fd.append("file", file); fd.append("doc_type", kind === "altele" ? "other" : kind);
        const { data } = await api.post("/ai/extract", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 240000 });
        mergedFiles.push(data.file);
        attached = true;
        if (data.warning) extractionWarnings.push(`${file.name}: ${data.warning}`);
        const x = data.data || {};
        if (kind === "ci") {
          const homeAddress = x.hq_address || x.address;
          mergedValues = putNonempty(mergedValues, { client_name: x.client_name, cnp: x.cnp, hq_address: homeAddress,
            ...(mergedValues.address_same_as_ci && homeAddress ? { address: homeAddress } : {}),
            county: x.county, locality: x.locality, phone: x.phone, email: x.email, id_series: x.id_series, id_number: x.id_number });
        }
        if (kind === "factura") mergedValues = putNonempty(mergedValues, { client_name: mergedValues.client_name || x.client_name, cnp: mergedValues.cnp || x.cnp,
          address: mergedValues.address_same_as_ci ? mergedValues.hq_address : x.consumption_address || x.address, postal_code: x.postal_code, pod: x.pod, nlc: x.nlc, operator: x.operator, supplier: x.supplier,
          county: mergedValues.county || x.county, locality: mergedValues.locality || x.locality, phone: mergedValues.phone || x.phone, email: mergedValues.email || x.email });
        if (kind === "factura" && !operatorManuallySet) {
          const suggestion = distributorSuggestion(mergedValues.pod, mergedValues.county);
          if (suggestion) mergedValues = { ...mergedValues, operator: suggestion };
        }
        if (kind === "cf") mergedValues = putNonempty(mergedValues, { cf_nr: x.cf_nr, cadastral_nr: x.cadastral_nr,
          client_name: mergedValues.client_name || x.owner_name });
        if (kind === "altele") mergedValues = putNonempty(mergedValues, { postal_code: x.postal_code, nlc: x.nlc });
        if (kind === "altele" && x.summary) summaries.push(`${file.name}: ${x.doc_type || "document"} — ${x.summary}`);
      } catch (error) {
        failed += 1;
        const reason = error.response?.data?.detail || error.message || "Eroare necunoscută la citirea documentului.";
        firstFailure ||= reason;
        if (!attached) {
          try {
            const fd = new FormData(); fd.append("file", file);
            const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
            mergedFiles.push(data);
            attachedWithoutRead += 1;
            extractionWarnings.push(`${file.name}: atașat, dar necitit automat (${reason}); verifică și completează manual.`);
          } catch (uploadError) {
            firstFailure = uploadError.response?.data?.detail || uploadError.message || reason;
          }
        }
      }
    }
    if (!operatorManuallySet) {
      const suggestion = distributorSuggestion(mergedValues.pod, mergedValues.county);
      if (suggestion) mergedValues = { ...mergedValues, operator: suggestion };
    }
    setFiles((prev) => ({ ...prev, [kind]: mergedFiles }));
    setValues(mergedValues);
    if (kind === "ci" || kind === "cf") setClientDetailsOpen(true);
    if (summaries.length) setNotes((prev) => ({ ...prev, altele: [...(prev.altele || []), ...summaries] }));
    if (extractionWarnings.length) setNotes((prev) => ({ ...prev, [kind]: [...(prev[kind] || []), ...extractionWarnings] }));
    const imported = mergedFiles.length - initialCount;
    if (attachedWithoutRead) toast.warning(`${attachedWithoutRead} documente atașate fără citire automată; verifică-le și completează manual. ${firstFailure}`);
    else if (failed && imported) toast.warning(`${imported} din ${list.length} documente atașate; ${failed} au necesitat verificare manuală. ${firstFailure}`);
    else if (failed) toast.error(firstFailure || `Nu s-au putut prelua ${failed} documente.`);
    else if (extractionWarnings.length) toast.warning(extractionWarnings[0]);
    else toast.success(`${list.length === 1 ? "Document citit" : `${list.length} documente citite`} — verifică datele extrase`);
    setBusy("");
    if (inputs.current[kind]) inputs.current[kind].value = "";
  };

  const create = async () => {
    if (!values.client_name.trim()) return toast.error("Completează sau corectează numele clientului din CI.");
    const filesForDossier = Object.entries(files).flatMap(([kind, list]) => list.map((f) => ({
      ...f, kind,
      doc_type: ({ ci: "Carte de identitate", factura: "Factură energie", cf: "Carte funciară", altele: "Document suplimentar" })[kind],
    })));
    const workflowBlockers = requiredDataMissing.map((field) => `Lipsește ${field}`);
    const payload = { ...values, client_name: values.client_name.trim(), files: filesForDossier,
      workflow_status: requiredDataMissing.length ? "Date de completat" : "Dosar în pregătire",
      workflow_blockers: workflowBlockers,
      notes: [...Object.values(notes).flat(), values.notes].filter(Boolean).join("\n") };
    try {
      setBusy("create");
      const { data } = await api.post("/import/prosumator", payload);
      toast.success(requiredDataMissing.length
        ? `Ciornă creată. Completează: ${requiredDataMissing.join(", ")}.`
        : "Clientul și dosarul au fost create cu documentele în opis.");
      setOpen(false); setStep(0); onCreated(data);
      setValues(EMPTY); setFiles({ ci: [], factura: [], cf: [], altele: [] }); setNotes({});
      setSelectedClient(null); setSelectedSiteId("new"); setClientSearch(""); setOperatorManuallySet(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Nu am putut crea dosarul"); }
    finally { setBusy(""); }
  };

  const field = (key, label) => <label className="den-field" key={key}><span>{label}</span>
    <input className="den-input" value={values[key] || ""} onChange={(e) => {
      const value = e.target.value;
      if (key === "operator") setOperatorManuallySet(Boolean(value.trim()));
      setValues((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "hq_address" && prev.address_same_as_ci) next.address = value;
      if ((key === "pod" || key === "county") && !operatorManuallySet) {
        next.operator = distributorSuggestion(next.pod, next.county);
      }
      return next;
    });
    }} data-testid={`intake-${key}`} /></label>;

  const requiredDataMissing = [
    ["CNP / CUI", values.cnp],
    ["adresa locului de consum", values.address],
    ["POD", values.pod],
    ["operatorul de distribuție", values.operator],
    ["județul", values.county],
    ["localitatea", values.locality],
  ].filter(([, value]) => !String(value || "").trim()).map(([label]) => label);

  return <>
    <Btn variant="secondary" onClick={() => setOpen(true)} data-testid="dossier-start-documents"><Plus size={15} /> Începe dosarul din documente</Btn>
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setStep(0); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="dossier-document-start-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Sparkles size={18} style={{ color: "var(--blue)" }} /> Dosar nou din documente</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Trei pași scurți. Încarcă actele, verifică datele extrase și apoi creează dosarul. AI preia doar informația identificată în documente.</p>
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="Pașii pentru dosarul nou">
          {["Client și acte", "Loc de consum", "Tip dosar"].map((label, index) => <button key={label} type="button" onClick={() => index <= step && setStep(index)} aria-current={step === index ? "step" : undefined} className="rounded-lg border px-2 py-2 text-left text-xs font-semibold" style={{ borderColor: step === index ? "var(--blue)" : "var(--line)", background: step === index ? "#eaf1ff" : "#fff", color: step === index ? "var(--blue)" : "var(--muted)" }}><span className="mr-1">{index + 1}.</span>{label}</button>)}
        </div>
        {step === 0 && <>
        <section className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
          <div className="mb-2 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Client existent sau client nou</div>
          {selectedClient ? <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: "#f2f7ff" }}>
            <span><b>{selectedClient.title}</b><span className="ml-2 text-xs" style={{ color: "var(--muted)" }}>{selectedClient.detail}</span></span>
            <button type="button" className="text-xs font-semibold underline" onClick={() => { setSelectedClient(null); setSelectedSiteId("new"); setClientSearch(""); setValues(EMPTY); setFiles({ ci: [], factura: [], cf: [], altele: [] }); setNotes({}); }}>Schimbă clientul</button>
          </div> : <>
            <input className="den-input" value={clientSearch} onChange={(event) => setClientSearch(event.target.value)} placeholder="Caută după nume, CNP/CUI sau telefon" aria-label="Caută un client existent" data-testid="intake-client-search" />
            {clientMatches.length > 0 && <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border" style={{ borderColor: "var(--line)" }} role="listbox" aria-label="Clienți găsiți">
              {clientMatches.map((client) => <button key={client.id} type="button" disabled={!!busy} className="block w-full border-b px-3 py-2 text-left last:border-b-0 hover:bg-slate-50 disabled:opacity-60" style={{ borderColor: "var(--line)" }} onClick={() => selectExistingClient(client)} data-testid={`intake-client-option-${client.id}`}><span className="block text-sm font-semibold">{busy === "client" ? "Încarc datele clientului…" : client.title}</span><span className="block text-xs" style={{ color: "var(--muted)" }}>{client.detail || "Date de contact necompletate"}</span></button>)}
            </div>}
            {!clientMatches.length && clientSearch.trim().length >= 2 && <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>Nu am găsit un client potrivit. Completează datele din CI mai jos pentru un client nou.</p>}
          </>}
        </section>
        <div className="grid sm:grid-cols-2 gap-2">
          {TYPES.map(([kind, title, help]) => <div key={kind} className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
            <div className="font-bold text-sm">{title}</div><p className="text-[11px] my-1" style={{ color: "var(--muted)" }}>{help}</p>
            <input ref={(el) => { inputs.current[kind] = el; }} type="file" accept={kind === "altele" ? ".pdf,image/*,.doc,.docx,.xls,.xlsx" : "application/pdf,image/*"} multiple={kind === "altele"} className="hidden"
              onChange={(e) => extract(kind, e.target.files)} data-testid={`intake-file-${kind}`} />
            <button onClick={() => inputs.current[kind]?.click()} disabled={!!busy} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }}>
              <Upload size={13} /> {busy === kind ? "AI citește…" : "Încarcă și citește"}
            </button>
            {(files[kind] || []).map((f) => <div key={f.storage_path} className="mt-1 text-[11px] flex gap-1 items-center"><FileText size={12} />{f.original_filename}</div>)}
            {notes[kind]?.length > 0 && <ul className="mt-2 list-disc pl-4 text-[11px] text-amber-700">{notes[kind].map((note, i) => <li key={i}>{note}</li>)}</ul>}
          </div>)}
        </div>
        <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} open={clientDetailsOpen} onToggle={(event) => setClientDetailsOpen(event.currentTarget.open)}>
          <summary className="cursor-pointer text-xs font-semibold">Verifică datele clientului{values.client_name ? ` · ${values.client_name}` : ""}{values.cnp ? ` · ${values.cnp}` : ""}</summary>
          <div className="space-y-3 pt-3">
          <section className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
            <div className="mb-2 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Date client din acte</div>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="den-field"><span>Tip client</span><select className="den-input" value={values.kind || ""} onChange={(e) => setValues((prev) => ({ ...prev, kind: e.target.value }))} data-testid="intake-client-kind"><option value="">Alege...</option><option value="Persoană fizică">Persoană fizică</option><option value="Persoană juridică">Persoană juridică</option></select></label>
              {field("client_name", "Nume client *")}{field("cnp", "CNP / CUI")}
              {field("id_series", "Serie CI")}{field("id_number", "Număr CI")}
              {field("hq_address", "Domiciliu din CI")}
            </div>
          </section>
          <section className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
            <div className="mb-2 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Imobil (dacă ai cartea funciară)</div>
            <div className="grid sm:grid-cols-2 gap-3">{field("cf_nr", "Număr carte funciară")}{field("cadastral_nr", "Număr cadastral")}</div>
          </section>
          <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <summary className="cursor-pointer text-xs font-semibold">Alte date client (opțional)</summary>
            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              {field("phone", "Telefon")}{field("email", "E-mail")}
            </div>
          </details>
          <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <summary className="cursor-pointer text-xs font-semibold">Date pentru regularizarea prosumatorului (opțional)</summary>
            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              {field("bank", "Bancă")}{field("iban", "IBAN")}
            </div>
          </details>
          </div>
        </details>
        </>}
        {step === 1 && <div className="space-y-3 pt-2">
          {selectedClient && <label className="den-field">
            <span>Loc de consum salvat pentru client</span>
            <select className="den-input" value={selectedSiteId} onChange={(event) => selectConsumptionSite(event.target.value)} data-testid="intake-consumption-site">
              <option value="new">Loc de consum nou pentru acest client</option>
              {(selectedClient.consumption_sites || []).map((site, index) => <option key={site.id} value={site.id}>{[site.address, site.locality, site.county, site.pod && ("POD " + site.pod)].filter(Boolean).join(" · ") || ("Loc de consum " + (index + 1))}</option>)}
            </select>
            <small>Locurile salvate se completează din nou în dosar. Alege „loc nou” pentru alt POD sau altă adresă.</small>
          </label>}
          <section className="rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }}>
            <div className="mb-2 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Loc de consum din factură</div>
            <div className="grid sm:grid-cols-2 gap-3">
              {field("address", "Adresa locului de consum")}{field("pod", "POD")}
              {field("operator", "Operator de distribuție")}{field("county", "Județ")}{field("locality", "Localitate")}
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Operatorul se propune după prefixul POD-ului sau județul din factură. Verifică propunerea; pentru rețele locale sau industriale selectează operatorul indicat în actele locului de consum.</p>
            <label className="mt-3 inline-flex items-center gap-2 text-xs font-medium" data-testid="intake-address-same-as-ci">
              <input type="checkbox" checked={values.address_same_as_ci === true} onChange={(e) => setValues((prev) => ({
                ...prev, address_same_as_ci: e.target.checked,
                ...(e.target.checked && prev.hq_address ? { address: prev.hq_address } : {}),
              }))} />
              Adresa locului de consum este aceeași cu adresa din CI
            </label>
          </section>
          <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <summary className="cursor-pointer text-xs font-semibold">Furnizor (dacă apare pe factură)</summary>
            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              {field("supplier", "Furnizor energie")}
            </div>
          </details>
          <details className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <summary className="cursor-pointer text-xs font-semibold">Coduri suplimentare din factură (opțional)</summary>
            <div className="grid sm:grid-cols-2 gap-3 mt-3">
              {field("nlc", "Cod loc de consum / NLC")}{field("postal_code", "Cod poștal")}
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>AI le completează numai dacă sunt vizibile în documentele încărcate; verifică valorile înainte de folosire.</p>
          </details>
        </div>}
        {step === 2 && <section className="rounded-lg border bg-white p-4" style={{ borderColor: "var(--line)" }}>
          <div className="mb-2 text-xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>Tipul dosarului de prosumator</div>
          {[
            ["Racordare prosumator — fără spor de putere", "Fără spor de putere", "Se pregătește notificarea aplicabilă operatorului (de regulă Anexa 2)."],
            ["Spor de putere + prosumator", "Cu spor de putere", "Se pregătește cererea de racordare aplicabilă operatorului (de regulă Anexa 1)."],
          ].map(([value, title, description]) => <label key={value} className="mb-2 flex items-start gap-3 rounded-lg border p-3 last:mb-0" style={{ borderColor: values.request_type === value ? "var(--blue)" : "var(--line)", background: values.request_type === value ? "#f7faff" : "#fff" }}>
            <input type="radio" name="dossier-kind" value={value} checked={values.request_type === value} onChange={() => setValues((prev) => ({ ...prev, request_type: value }))} className="mt-1" data-testid={value.includes("spor") ? "intake-request-type-increase" : "intake-request-type-standard"} />
            <span><b className="block text-sm">{title}</b><span className="text-xs" style={{ color: "var(--muted)" }}>{description}</span></span>
          </label>)}
          {requiredDataMissing.length > 0 ? <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900" role="status" data-testid="intake-missing-data">
            <b>Ciornă — date de completat</b>
            <p className="mt-1">Dosarul poate fi salvat acum și completat ulterior. Pentru pregătirea depunerii lipsesc: {requiredDataMissing.join(", ")}.</p>
          </div> : <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900" role="status" data-testid="intake-data-ready">
            <b>Datele de bază sunt prezente.</b>
            <p className="mt-1">Verifică valorile extrase și documentele înainte de pregătirea pentru depunere.</p>
          </div>}
          <div className="mt-3 rounded-lg p-3 text-xs" style={{ background: "var(--bg)", color: "var(--muted)" }}>Documentele încărcate rămân atașate dosarului și apar în opis. Verifică datele extrase; formularele exacte depind de operator și se verifică înainte de depunere.</div>
        </section>}
        {notes.altele?.length > 0 && <div className="rounded-lg bg-slate-50 p-3 text-xs"><b>Documente suplimentare:</b><ul className="list-disc pl-5">{notes.altele.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
        <div className="flex justify-between gap-2 pt-2"><div>{step > 0 && <Btn variant="secondary" onClick={() => setStep((current) => current - 1)} disabled={!!busy}>Înapoi</Btn>}</div><div className="flex gap-2"><Btn variant="secondary" onClick={() => setOpen(false)}>Închide</Btn>
          {step < 2 ? <Btn onClick={() => { if (step === 0 && !values.client_name.trim()) return toast.error("Încarcă CI-ul sau completează numele clientului pentru a continua."); setStep((current) => current + 1); }} disabled={!!busy} data-testid="dossier-start-next">Continuă</Btn> : <Btn onClick={create} disabled={!!busy || !values.client_name.trim()} data-testid="dossier-start-create">{busy === "create" ? "Creez dosarul…" : "Creează dosarul"}</Btn>}</div></div>
      </DialogContent>
    </Dialog>
  </>;
}



