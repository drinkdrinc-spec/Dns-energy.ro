import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X, LayoutGrid, List, Filter, ChevronRight, Archive } from "lucide-react";
import { toast } from "sonner";
import { AiImportButton, GeneratedDocs } from "@/components/ProsumatorTools";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs } from "@/components/dossier/ClientDocs";
import { SignRequests } from "@/components/sign/SignRequests";
import { SldPanel } from "@/components/sld/SldPanel";
import { AssignBox } from "@/components/AssignBox";
import { useAuth } from "@/context/AuthContext";
import { PowerDossier, SimpleDossierBtn } from "@/components/dossier/PowerDossier";
import { AtrDossier } from "@/components/dossier/AtrDossier";
import { PifPanel } from "@/components/dossier/PifPanel";
import { AiDossierCheck } from "@/components/ai/AiDossierCheck";
import { AiDraft } from "@/components/ai/AiDraft";
import { DiuDossier } from "@/components/dossier/DiuDossier";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { can } from "@/lib/plan";
import { DossierTimeline } from "@/components/dossier/DossierTimeline";
import { DossierMessages } from "@/components/dossier/DossierMessages";

const PROSUM_STATUS_MAP = { "În pregătire": "CER", "Depus la operator": "Dosar depus", "ATR emis": "Factură ATR", "În execuție": "Așteaptă instalare", "Punere în funcțiune": "PV Teste / PIF", "Prosumator activ": "Finalizat" };
const displayStatus = (item) => PROSUM_STATUS_MAP[item.status] || item.status || "CER";

function Field({ f, value, onChange, refOptions, ai, allowNewReference = false }) {
  if (f.type === "section") return <h3 className="sm:col-span-2 mt-3 pt-3 border-t text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h3>;
  const common = { className: "den-input", value: value ?? "", onChange: (e) => onChange(f.name, e.target.value), placeholder: f.placeholder || "", "data-testid": `field-${f.name}` };
  return (
    <div className={`den-field ${f.full ? "sm:col-span-2" : ""}`}>
      <label>{f.label}</label>
      {f.type === "textarea" ? (
        <><textarea {...common} rows={3} />{ai && <AiDraft module={ai.module} field={f.name} label={f.label} form={ai.form} onApply={onChange} />}</>
      ) : f.type === "select" ? (
        <select {...common}><option value="">Alege...</option>{value && !f.options.includes(value) && <option value={value}>{value}</option>}{f.options.map((o) => <option key={o} value={o}>{o}</option>)}</select>
      ) : f.type === "ref" && allowNewReference ? (
        <><input {...common} list={`options-${f.name}`} autoComplete="off" /><datalist id={`options-${f.name}`}>{(refOptions[f.ref] || []).map((o) => <option key={o.id} value={o.label} />)}</datalist>
          <div className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>Alege un client existent sau scrie numele unui client nou; acesta va fi adăugat automat în registru la salvarea dosarului.</div></>
      ) : f.type === "ref" ? (
        <select {...common}><option value="">Alege...</option>{value && !(refOptions[f.ref] || []).some((o) => o.label === value) && <option value={value}>{value} (nou)</option>}{(refOptions[f.ref] || []).map((o) => <option key={o.id} value={o.label}>{o.label}</option>)}</select>
      ) : (
        <input {...common} type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} step={f.type === "number" ? "any" : undefined} />
      )}
    </div>
  );
}

const DOSSIER_SECTION_PAGE = {
  "Client": "client",
  "Loc de consum": "site",
  "Cererea": "request",
  "Date tehnice": "installation",
  "Date documente dosar": "documents",
  "Recepție la terminarea lucrărilor": "documents",
  "Punere în funcțiune și teste": "documents",
  "Buletin priză de pământ (valori măsurate)": "documents",
  "Tablou general și alimentare": "documents",
  "Recepție, punere în funcțiune și garanție": "documents",
};

function DossierFieldSections({ fields, page, form, setVal, refOptions, ai }) {
  const sections = [];
  let current = { label: "Date dosar", fields: [] };
  const pushSection = (section) => {
    if (section.label !== "Client și loc de consum") { sections.push(section); return; }
    const siteFields = new Set(["address", "county", "locality", "pod", "operator", "cadastral_nr", "cf_nr", "supplier"]);
    const client = section.fields.filter((field) => !siteFields.has(field.name));
    const site = section.fields.filter((field) => siteFields.has(field.name));
    if (client.length) sections.push({ label: "Client", fields: client });
    if (site.length) sections.push({ label: "Loc de consum", fields: site });
  };
  fields.forEach((field) => {
    if (field.type === "section") {
      if (current.fields.length) pushSection(current);
      current = { label: field.label, fields: [] };
    } else current.fields.push(field);
  });
  if (current.fields.length) pushSection(current);

  return <div className="space-y-4" data-testid="dossier-section-cards">
    {sections.filter((section) => page === "all" || (["client", "site", "request", "installation", "documents"].includes(page) && (DOSSIER_SECTION_PAGE[section.label] || "client") === page)).map((section) => (
      <section key={section.label} className="den-panel !p-0 overflow-hidden" data-testid={`dossier-section-${section.label}`}>
        <div className="flex items-center gap-2 border-b px-4 py-3 sm:px-5" style={{ borderColor: "var(--line)" }}>
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--green)" }} aria-hidden="true" />
          <h3 className="text-sm font-bold">{section.label}</h3>
        </div>
        <div className="grid sm:grid-cols-2 gap-4 p-4 sm:p-5">
          {section.fields.map((field) => <Field key={field.name} f={field} value={form[field.name]} onChange={setVal} refOptions={refOptions} ai={ai} />)}
        </div>
      </section>
    ))}
  </div>;
}

function SummaryStrip({ form }) {
  const metrics = [
    ["Stadiu", displayStatus(form)], ["Operator", form.operator || "Neales"],
    ["Putere CEF", form.power ? `${form.power} kW` : "Necompletată"],
    ["Panouri", form.panel_count ? `${form.panel_count} buc.` : "Necompletat"],
    ["Stocare", form.battery_kwh ? `${form.battery_kwh} kWh` : "Fără baterie"],
  ];
  return <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 rounded-xl border p-3 mb-5" style={{ borderColor: "var(--line)", background: "#fffefa" }} data-testid="dossier-live-summary">
    {metrics.map(([label, value]) => <div key={label} className="min-w-0 rounded-lg px-3 py-2" style={{ background: "var(--bg)" }}>
      <div className="text-[9px] font-bold uppercase tracking-wider" style={{ color: "var(--muted)" }}>{label}</div>
      <div className="mt-1 truncate text-xs font-bold" title={value}>{value}</div>
    </div>)}
  </div>;
}

export default function ModulePage({ moduleKey }) {
  const params = useParams();
  const key = moduleKey || params.module;
  const cfg = MODULES[key];
  const { user } = useAuth();
  const role = user?.role || "admin";
  const canDelete = role === "admin" || (role !== "limitat" && !["prosumator", "clients"].includes(key));
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null); // null=hidden, {} = open
  const [editId, setEditId] = useState(null);
  const [checks, setChecks] = useState({});
  const [refOptions, setRefOptions] = useState({});
  const [clientRecords, setClientRecords] = useState([]);
  const [q, setQ] = useState("");
  const [savedAt, setSavedAt] = useState(0);
  const [diuPre, setDiuPre] = useState(false);
  const [prosumStep, setProsumStep] = useState(1);
  const [newProsumClient, setNewProsumClient] = useState(false);
  const [dossierPage, setDossierPage] = useState("client");
  const [dossierView, setDossierView] = useState("list");
  const [operatorFilter, setOperatorFilter] = useState("");
  const [countyFilter, setCountyFilter] = useState("");
  const [localityFilter, setLocalityFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [archiveView, setArchiveView] = useState(false);

  const load = () => api.get(`/data/${key}`).then((r) => {
    setItems(r.data);
    const params = new URLSearchParams(window.location.search);
    const eid = params.get("edit");
    const it = eid && r.data.find((x) => x.id === eid);
    const startNew = key === "prosumator" && params.get("new") === "1";
    if (it) { setForm({ ...it }); setEditId(it.id); setChecks(it.checklist || {}); setDossierPage("all"); }
    else if (startNew) { setForm({ doc_date: new Date().toISOString().slice(0, 10), status: "CER", kind: "Persoană fizică" }); setEditId(null); setChecks({}); setProsumStep(1); setNewProsumClient(false); setDossierPage("site"); }
    if (it || startNew) window.history.replaceState(null, "", window.location.pathname);
  }).catch(() => {});

  useEffect(() => {
    setForm(null); setEditId(null); setChecks({}); setQ("");
    load();
    const refs = [...new Set((cfg.fields || []).filter((f) => f.type === "ref").map((f) => f.ref))];
    refs.forEach((ref) => {
      api.get(`/data/${ref}`).then((r) => {
        if (key === "prosumator" && ref === "clients") setClientRecords(r.data);
        setRefOptions((prev) => ({ ...prev, [ref]: r.data.map((x) => ({ id: x.id, label: MODULES[ref].display(x) })) }));
      }).catch(() => {});
    });
    // eslint-disable-next-line
  }, [key]);

  const openNew = () => { setForm(key === "prosumator" ? { doc_date: new Date().toISOString().slice(0, 10), status: "CER", kind: "Persoană fizică" } : {}); setEditId(null); setChecks({}); setProsumStep(1); setNewProsumClient(false); setDossierPage("site"); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); setProsumStep(1); setDossierPage("all"); };
  const setVal = (name, value) => setForm((p) => {
    const next = { ...p, [name]: value };
    if (key === "prosumator" && name === "client_name") {
      const client = clientRecords.find((c) => c.name?.trim().toLocaleLowerCase() === value.trim().toLocaleLowerCase());
      if (client) Object.assign(next, {
        kind: client.kind || "Persoană fizică", cnp: client.idcode || "", ci_series: client.ci_series || "", regcom: client.regcom || "", bank: client.bank || "", iban: client.iban || "", rep_role: client.rep_role || "",
        phone: client.phone || "", email: client.email || "", address: client.address || "",
        hq_address: client.hq_address || "", county: client.county || "", locality: client.locality || "", pod: client.pod || "", operator: client.operator || "",
        cadastral_nr: client.cadastral_nr || "", cf_nr: client.cf_nr || "", supplier: client.supplier || "", rep_name: client.rep_name || "",
      });
    }
    return next;
  });
  const continueProsum = () => {
    if (prosumStep === 1 && !form.client_name?.trim()) { toast.error("Introdu numele beneficiarului sau alege un client existent."); return; }
    if (prosumStep === 1 && !newProsumClient && !clientRecords.some((client) => client.name?.trim().toLocaleLowerCase() === form.client_name.trim().toLocaleLowerCase())) { toast.error("Alege un client existent sau selectează Client nou."); return; }
    if (prosumStep === 2 && !form.address?.trim() && !form.pod?.trim()) { toast.error("Completează adresa locului de consum sau codul POD."); return; }
    if (prosumStep === 3 && !form.request_type) { toast.error("Alege tipul cererii."); return; }
    setProsumStep((s) => Math.min(3, s + 1));
  };

  const save = async () => {
    if (key === "prosumator" && !editId && !form.request_type) { toast.error("Alege tipul cererii înainte de creare."); return; }
    const orig = items.find((i) => i.id === editId);
    if (key === "diu" && editId && form.status === "Predat beneficiarului" && orig?.status !== "Predat beneficiarului" && can(user, "ai_gpt")) { setDiuPre(true); return; }
    return doSave().catch(() => {});
  };
  const doSave = async () => {
    const required = (cfg.fields || []).filter((f) => f.required);
    for (const f of required) { if (!form[f.name]) { toast.error(`Completează: ${f.label.replace(" *", "")}`); return; } }
    const payload = { ...form };
    if (cfg.checklist) payload.checklist = checks;
    try {
      if (editId) await api.put(`/data/${key}/${editId}`, payload);
      else if (key === "prosumator") {
        const created = await api.post("/import/prosumator", payload);
        toast.success("Dosar creat. Poți continua completarea documentației mai jos.");
        setForm(created.data); setEditId(created.data.id); setChecks(created.data.checklist || {}); setProsumStep(1); setDossierPage("all"); load();
        return;
      }
      else await api.post(`/data/${key}`, payload);
      toast.success("Salvat cu succes");
      if (key === "diu" && editId) { setSavedAt(Date.now()); load(); return; }
      setForm(null); setEditId(null); setChecks({}); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eroare la salvare"); throw e; }
  };

  const remove = async (id) => {
    if (!window.confirm("Ștergi această înregistrare?")) return;
    await api.delete(`/data/${key}/${id}`);
    toast.success("Șters"); load();
  };

  const statusOptions = (cfg.fields || []).find((f) => f.name === "status")?.options || [];
  const archiveCutoffDate = new Date();
  archiveCutoffDate.setMonth(archiveCutoffDate.getMonth() - 6);
  const archiveCutoff = archiveCutoffDate.getTime();
  const isArchived = (item) => {
    const lastActivity = Date.parse(item.updated_at || item.created_at || "");
    return Number.isFinite(lastActivity) && lastActivity < archiveCutoff;
  };
  const archiveCount = key === "prosumator" ? items.filter(isArchived).length : 0;
  const activeItems = key === "prosumator" ? items.filter((item) => isArchived(item) === archiveView) : items;
  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return activeItems.filter((i) => (!ql || JSON.stringify(i).toLowerCase().includes(ql))
      && (!operatorFilter || i.operator === operatorFilter)
      && (!countyFilter || i.county === countyFilter)
      && (!localityFilter || i.locality === localityFilter)
      && (!clientFilter || String(i.client_name || "").toLocaleLowerCase("ro").includes(clientFilter.toLocaleLowerCase("ro"))));
  }, [activeItems, q, operatorFilter, countyFilter, localityFilter, clientFilter]);

  const changeStatus = async (item, status) => {
    try {
      await api.patch(`/data/${key}/${item.id}/status`, { status });
      setItems((prev) => prev.map((i) => i.id === item.id ? { ...i, status, updated_at: new Date().toISOString() } : i));
      toast.success("Stadiul dosarului a fost actualizat");
    } catch (e) { toast.error(e.response?.data?.detail || "Stadiul nu a putut fi actualizat"); }
  };
  const dragId = (e) => e.dataTransfer?.getData("text/plain");
  const optionValues = (key) => [...new Set(items.map((i) => i[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ro"));

  const checkedCount = cfg.checklist ? cfg.checklist.filter((c) => checks[c]).length : 0;

  return (
    <div>
      <PageHeader eyebrow={cfg.eyebrow} title={cfg.title} sub={cfg.sub}
        action={<div className="flex gap-2 flex-wrap">
          {key === "prosumator" && <AiImportButton onExtracted={(d) => { setForm(d); setEditId(null); setChecks({}); }} />}
          <Btn data-testid="add-btn" onClick={form ? () => setForm(null) : openNew}>{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> {cfg.addLabel}</>}</Btn>
        </div>} />

      {form && (
        <div className="den-panel mb-6" data-testid="module-form">
          {key === "prosumator" && !editId ? <>
            <div className="flex items-start justify-between gap-4 mb-5">
              <div className="mb-4"><h2 className="text-lg font-bold">Dosar nou</h2><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Alegi clientul, locul de consum și cererea; restul datelor le completezi după.</p></div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-5" aria-label={`Pasul ${prosumStep} din 3`}>
              {["Client", "Loc de consum", "Tip cerere"].map((step, idx) => <div key={step} className={`rounded-lg border px-2 py-2 text-center text-[10px] sm:text-[11px] font-semibold ${prosumStep === idx + 1 ? "den-wizard-active" : ""}`} style={{ borderColor: prosumStep === idx + 1 ? "var(--green)" : "var(--line)", color: prosumStep === idx + 1 ? "var(--green)" : "var(--muted)", background: prosumStep === idx + 1 ? "#edf7f0" : "transparent" }}><span className="mr-1 inline-grid h-4 w-4 place-items-center rounded-full" style={{ background: prosumStep > idx + 1 ? "var(--green)" : "#eeeae1", color: prosumStep > idx + 1 ? "white" : "var(--muted)" }}>{prosumStep > idx + 1 ? "✓" : idx + 1}</span>{step}</div>)}
            </div>
          </> : <h2 className="text-lg font-bold mb-5">{editId ? (key === "prosumator" ? `Dosar ${form.number || "prosumator"} · documentație` : "Editează înregistrarea") : cfg.addLabel}</h2>}
          {key === "prosumator" && editId && <div className="mb-5 flex gap-2 overflow-x-auto border-b pb-2" role="tablist" aria-label="Pagini dosar">
            {[ ["all", "Dosar complet"], ["client", "Client"], ["site", "Loc de consum"], ["request", "Cererea"], ["installation", "Instalație"], ["documents", "Acte & semnare"], ["equipment", "Echipamente"], ["team", "Echipă"], ["pif", "Teste și PIF"], ["other", "Mesaje & asignare"], ["timeline", "Jurnal"] ].map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={dossierPage === id} onClick={() => setDossierPage(id)} className="shrink-0 rounded-lg px-3 py-2 text-xs font-bold" style={dossierPage === id ? { background: "var(--navy)", color: "white" } : { background: "var(--bg)", color: "var(--muted)" }} data-testid={`dossier-page-${id}`}>{label}</button>)}
          </div>}
          {key === "prosumator" && editId && <SummaryStrip form={form} />}
          {key === "prosumator" && !editId && prosumStep === 1 && <div className="mb-4 flex flex-wrap items-center gap-2" data-testid="prosum-client-mode">
            <button type="button" onClick={() => setNewProsumClient(false)} className="rounded-lg border px-3 py-2 text-xs font-bold" style={!newProsumClient ? { background: "var(--green)", color: "white", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Client existent</button>
            <button type="button" onClick={() => { setNewProsumClient(true); setForm((prev) => ({ ...prev, client_name: "", kind: "Persoană fizică", cnp: "", ci_series: "", regcom: "", phone: "", email: "", hq_address: "", bank: "", iban: "", rep_name: "", rep_role: "", address: "", county: "", locality: "", pod: "", operator: "", cadastral_nr: "", cf_nr: "", supplier: "" })); }} className="rounded-lg border px-3 py-2 text-xs font-bold" style={newProsumClient ? { background: "var(--green)", color: "white", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Client nou</button>
            {newProsumClient && <div className="flex gap-2"><button type="button" onClick={() => setVal("kind", "Persoană fizică")} className="rounded-lg border px-3 py-2 text-xs font-bold" style={form.kind === "Persoană fizică" ? { background: "#edf7f0", color: "var(--green)", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Persoană fizică</button><button type="button" onClick={() => setVal("kind", "Persoană juridică")} className="rounded-lg border px-3 py-2 text-xs font-bold" style={form.kind === "Persoană juridică" ? { background: "#edf7f0", color: "var(--green)", borderColor: "var(--green)" } : { borderColor: "var(--line)" }}>Persoană juridică</button></div>}
          </div>}
          {key === "prosumator" && editId ? <DossierFieldSections fields={cfg.fields} page={dossierPage} form={form} setVal={setVal} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} /> : <div className="grid sm:grid-cols-2 gap-4">
            {cfg.fields.map((f, i) => {
              if (key === "prosumator" && !editId) {
                const steps = {
                  1: ["client_name"],
                  2: ["address", "county", "locality", "pod", "operator"],
                  3: ["request_type", "supply", "afm"],
                };
                if (!steps[prosumStep].includes(f.name)) return null;
                if (prosumStep === 1 && !newProsumClient && f.name !== "client_name") return null;
                if (prosumStep === 1 && newProsumClient && f.name === "kind") return null;
                if (prosumStep === 1 && newProsumClient && f.name === "regcom" && form.kind !== "Persoană juridică") return null;
                if (prosumStep === 1 && newProsumClient && f.name === "rep_role" && form.kind !== "Persoană juridică") return null;
              } else if (key === "prosumator" && !editId && f.type === "section") return null;
              return <Field key={f.name || `s${i}`} f={f} value={form[f.name]} onChange={setVal} refOptions={refOptions} allowNewReference={key === "prosumator" && f.name === "client_name"} ai={can(user, "ai_gpt") ? { module: key, form } : null} />;
            })}
          </div>}

          {key === "prosumator" && !editId && <div className="flex items-center justify-between gap-2 mt-6 border-t pt-4" style={{ borderColor: "var(--line)" }}>
            <div className="flex gap-2"><Btn variant="secondary" onClick={() => setForm(null)}>Renunță</Btn>{prosumStep > 1 && <Btn variant="secondary" onClick={() => setProsumStep((s) => s - 1)}>Înapoi</Btn>}</div>
            {prosumStep < 3 ? <Btn onClick={continueProsum}>Continuă</Btn> : <Btn onClick={save} data-testid="save-btn"><Plus size={15} /> Creează dosarul</Btn>}
          </div>}

          {cfg.checklist && (key !== "prosumator" || (!!editId && ["documents", "all"].includes(dossierPage))) && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-sm">Checklist documente — {cfg.title}</h3>
                <span className="text-[11px] font-bold px-3 py-1 rounded-full" style={{ background: "#eef4ff", color: "var(--blue)" }}>{checkedCount} / {cfg.checklist.length} bifate</span>
              </div>
              <div className="grid sm:grid-cols-2 gap-2">
                {cfg.checklist.map((c) => (
                  <label key={c} className="flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer text-sm" style={{ borderColor: "var(--line)" }}>
                    <input type="checkbox" checked={!!checks[c]} onChange={(e) => setChecks((p) => ({ ...p, [c]: e.target.checked }))} data-testid={`check-${c}`} />
                    <span>{c}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {key === "prosumator" && editId && ["documents", "all"].includes(dossierPage) && <><DossierOpis id={editId} /><GeneratedDocs id={editId} files={form.files} /><SignRequests dossierId={editId} /></>}
          {key === "prosumator" && editId && ["equipment", "all"].includes(dossierPage) && <><div className="mt-2"><h3 className="font-bold text-base">Echipamente și parametri instalației</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Selectează modelul din catalog pentru a prelua datele tehnice și a verifica fișele disponibile.</p><CefEditor value={form.cef} onChange={(v) => setVal("cef", v)} /></div><SldPanel id={editId} form={form} setVal={setVal} /></>}
          {key === "prosumator" && editId && ["team", "all"].includes(dossierPage) && <DossierExtras form={form} setVal={setVal} view="team" />}
          {key === "prosumator" && editId && dossierPage === "pif" && <DossierExtras form={form} setVal={setVal} view="pif" />}
          {key === "prosumator" && editId && ["pif", "all"].includes(dossierPage) && <><h3 className="mt-6 font-bold text-base">Reglaje și punere în funcțiune</h3>{dossierPage === "all" && <DossierExtras form={form} setVal={setVal} view="pif" />}<PifPanel id={editId} /></>}
          {key === "prosumator" && editId && ["other", "all"].includes(dossierPage) && <><AssignBox value={form.assigned_to} onChange={(v) => setVal("assigned_to", v)} /><DossierMessages id={editId} /><SimpleDossierBtn id={editId} /><AiDossierCheck id={editId} /></>}
          {key === "prosumator" && editId && ["timeline", "all"].includes(dossierPage) && <DossierTimeline id={editId} />}
          {key === "power" && <PowerDossier id={editId} form={form} setVal={setVal} />}
          {key === "atr" && <AtrDossier id={editId} form={form} setVal={setVal} />}
          {key === "diu" && editId && <DiuDossier id={editId} form={form} setVal={setVal} setForm={setForm} savedAt={savedAt} />}
          {key === "diu" && editId && <SignRequests dossierId={editId} module="diu" />}
          {key === "diu" && editId && <AiPrecheck id={editId} base="diu" open={diuPre} onClose={() => setDiuPre(false)} onFinalize={doSave} form={form}
            title="Verificare AI înainte de predarea către beneficiar" action="Salvează ca „Predat beneficiarului”" />}
          {key === "clients" && editId && <ClientDocs client={form} onChange={(docs) => setVal("docs", docs)} />}
          {key === "clients" && editId && <SignRequests clientName={form.name} />}

          {!(key === "prosumator" && !editId) && <div className={`flex gap-2 mt-6 den-noprint ${key === "prosumator" && editId ? "sticky bottom-2 z-20 rounded-xl border bg-white/95 p-3 shadow-lg backdrop-blur" : ""}`} style={key === "prosumator" && editId ? { borderColor: "var(--line)" } : undefined}>
            <Btn onClick={save} data-testid="save-btn">Salvează</Btn>
            <Btn variant="secondary" onClick={() => window.print()} data-testid="pdf-btn">Tipărește / PDF</Btn>
            <Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>
          </div>}
        </div>
      )}

      <div className="den-panel">
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <div><h2 className="text-lg font-bold">Dosare {key === "prosumator" ? (archiveView ? "arhivate" : "active") : "salvate"} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({filtered.length})</span></h2>{key === "prosumator" && <p className="mt-1 text-[10px]" style={{ color: "var(--muted)" }}>{archiveView ? "Fără activitate în ultimele 6 luni; la actualizare revin la dosarele active." : "Dosarele fără activitate timp de 6 luni se arhivează automat."}</p>}</div>
          <div className="flex flex-wrap items-center gap-2">
          {key === "prosumator" && <div className="flex rounded-lg border p-1" style={{ borderColor: "var(--line)" }}>
            <button onClick={() => setArchiveView(false)} className={`rounded-md px-3 py-2 text-[11px] font-bold ${!archiveView ? "text-white" : ""}`} style={!archiveView ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-active-dossiers">Active ({items.length - archiveCount})</button>
            <button onClick={() => setArchiveView(true)} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${archiveView ? "text-white" : ""}`} style={archiveView ? { background: "var(--navy)" } : { color: "var(--muted)" }} data-testid="view-archived-dossiers"><Archive size={13} /> Arhivate ({archiveCount})</button>
          </div>}
          {key === "prosumator" && <div className="flex rounded-lg border p-1" style={{ borderColor: "var(--line)" }}>
            <button onClick={() => setDossierView("kanban")} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${dossierView === "kanban" ? "text-white" : ""}`} style={dossierView === "kanban" ? { background: "var(--green)" } : { color: "var(--muted)" }} data-testid="view-kanban"><LayoutGrid size={14} /> Kanban</button>
            <button onClick={() => setDossierView("list")} className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[11px] font-bold ${dossierView === "list" ? "text-white" : ""}`} style={dossierView === "list" ? { background: "var(--green)" } : { color: "var(--muted)" }} data-testid="view-list"><List size={14} /> Listă</button>
          </div>}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input data-testid="search-input" className="den-input w-[240px]" style={{ paddingLeft: 34 }} placeholder="Caută..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          </div>
        </div>

        {key === "prosumator" && <div className="mb-4 flex flex-wrap items-end gap-2 rounded-xl p-3" style={{ background: "var(--bg)" }} data-testid="dossier-filters">
          <span className="mr-1 inline-flex items-center gap-1.5 self-center text-[11px] font-bold" style={{ color: "var(--muted)" }}><Filter size={14} /> Filtre</span>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrează după operator">
            {optionValues("operator").map((op) => <button key={op} type="button" aria-pressed={operatorFilter === op} onClick={() => setOperatorFilter(operatorFilter === op ? "" : op)} className="rounded-full border px-3 py-2 text-[11px] font-bold transition-colors" style={operatorFilter === op ? { background: "var(--green)", color: "#fff", borderColor: "var(--green)" } : { background: "#fff", color: "var(--ink)", borderColor: "var(--line)" }} data-testid={`filter-operator-${op}`}>{op}</button>)}
          </div>
          {[["Județ", "county", countyFilter, setCountyFilter], ["Localitate", "locality", localityFilter, setLocalityFilter]].map(([label, field, value, set]) => <label key={field} className="den-field min-w-[150px]"><span className="sr-only">{label}</span><select className="den-input !py-2" value={value} onChange={(e) => set(e.target.value)} aria-label={label}><option value="">Toate — {label.toLowerCase()}</option>{optionValues(field).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>)}
          <label className="den-field min-w-[170px]"><span className="sr-only">Client</span><input className="den-input !py-2" value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} placeholder="Client…" aria-label="Client" data-testid="filter-client" /></label>
          {(operatorFilter || countyFilter || localityFilter || clientFilter) && <button className="px-2 py-2 text-[11px] font-bold" style={{ color: "var(--blue)" }} onClick={() => { setOperatorFilter(""); setCountyFilter(""); setLocalityFilter(""); setClientFilter(""); }}>Șterge filtrele</button>}
          <span className="ml-auto self-center text-[11px]" style={{ color: "var(--muted)" }}>{filtered.length} / {items.length} dosare</span>
        </div>}

        {filtered.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>{archiveView ? "Nu există dosare arhivate." : (items.length ? "Nu există dosare care să corespundă filtrelor." : "Nu există înregistrări încă.")}</div>
        ) : key === "prosumator" && dossierView === "kanban" ? (
          <div className="flex gap-3 overflow-x-auto pb-3" data-testid="dossier-kanban">
            {statusOptions.map((status) => {
              const cards = filtered.filter((item) => displayStatus(item) === status);
              return <section key={status} className="w-[260px] shrink-0 rounded-xl p-3" style={{ background: "#f5f7fb" }} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const item = items.find((i) => i.id === dragId(e)); if (item && item.status !== status) changeStatus(item, status); }} data-testid={`kanban-column-${status}`}>
                <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-[10px] font-extrabold uppercase tracking-wide">{status}</h3><span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "#e8edf5", color: "var(--muted)" }}>{cards.length}</span></div>
                <div className="space-y-2 min-h-10">{cards.map((item) => <article key={item.id} draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", item.id)} className="rounded-xl border bg-white p-3 shadow-sm cursor-grab" style={{ borderColor: item.blocker?.active ? "#e8a1a1" : "var(--line)" }} data-testid={`kanban-card-${item.id}`}>
                  <button className="w-full text-left" onClick={() => openEdit(item)}><span className="block text-[10px] font-bold" style={{ color: "var(--blue)" }}>{item.number || "Fără număr"}</span><b className="mt-1 block text-[12px]">{item.client_name || "Beneficiar neprecizat"}</b><span className="mt-1 block truncate text-[10px]" style={{ color: "var(--muted)" }}>{[item.locality, item.county].filter(Boolean).join(", ") || item.address || "Loc de consum necompletat"}</span>{item.blocker?.active && <span className="mt-2 block rounded-md px-2 py-1 text-[10px] font-semibold" style={{ color: "#9b2c2c", background: "#fff0f0" }}>Blocaj: {item.blocker.title}</span>}</button>
                  <div className="mt-2 flex items-center justify-between border-t pt-2" style={{ borderColor: "var(--line)" }}><span className="truncate text-[9px]" style={{ color: "var(--muted)" }}>{item.operator || "Operator neprecizat"}</span><button className="rounded-md p-1 hover:bg-slate-100" title="Editează dosarul" onClick={() => openEdit(item)}><ChevronRight size={14} /></button></div>
                </article>)}</div>
              </section>;
            })}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="items-table">
              <thead>
                <tr className="text-left" style={{ background: "var(--green)", color: "#fff" }}>
                  {cfg.columns.map((c) => <th key={c.key} className="px-3 py-2.5 font-extrabold uppercase tracking-wider text-[10px] whitespace-nowrap">{c.label}</th>)}
                  <th className="px-3 py-2.5 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <tr key={it.id} className="border-t hover:bg-[#fafcff]" style={{ borderColor: "var(--line)" }}>
                    {cfg.columns.map((c) => <td key={c.key} className="px-3 py-3 whitespace-nowrap">{c.key === "status" && statusOptions.length ? <div className="inline-flex items-center gap-2"><select aria-label={`Stadiul ${key === "prosumator" ? "dosar" : "înregistrării"} ${it.number || it.title || ""}`} data-testid={`status-${it.id}`} className="cursor-pointer rounded-full border-0 px-2.5 py-1 text-[11px] font-bold focus:ring-2 focus:ring-blue-400" style={{ background: "#edf7f0", color: "var(--green)", maxWidth: "100%" }} value={(key === "prosumator" ? displayStatus(it) : it.status) || ""} onClick={(e) => e.stopPropagation()} onChange={(e) => changeStatus(it, e.target.value)}><option value="" disabled>Alege stadiul</option>{statusOptions.map((status) => <option key={status} value={status}>{status}</option>)}</select>{key === "prosumator" && it.blocker?.active && <span className="rounded-full px-2 py-1 text-[10px] font-bold" style={{ color: "#9b2c2c", background: "#fff0f0" }}>Blocaj</span>}</div> : c.key === "blocker" ? (it.blocker?.active ? <span className="rounded-full px-2 py-1 text-[10px] font-bold" style={{ color: "#9b2c2c", background: "#fff0f0" }}>{it.blocker.title || "Activ"}</span> : "—") : it[c.key] || "—"}</td>)}
                    <td className="px-3 py-3 text-right whitespace-nowrap">
                      <button onClick={() => openEdit(it)} data-testid={`edit-${it.id}`} className="p-1.5 rounded hover:bg-[#eef4ff]" title="Editează"><Pencil size={15} style={{ color: "var(--blue)" }} /></button>
                      {canDelete && <button onClick={() => remove(it.id)} data-testid={`delete-${it.id}`} className="p-1.5 rounded hover:bg-[#fff0f0] ml-1" title="Șterge"><Trash2 size={15} style={{ color: "#b33333" }} /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

