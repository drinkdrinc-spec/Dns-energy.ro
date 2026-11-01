import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, API, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X } from "lucide-react";
import { toast } from "sonner";
import { GeneratedDocs } from "@/components/ProsumatorTools";
import { DossierDocumentStart } from "@/components/dossier/DossierDocumentStart";
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
import { AiRacordCheck } from "@/components/ai/AiRacordCheck";
import { AiOdReview } from "@/components/ai/AiOdReview";
import { AiDraft } from "@/components/ai/AiDraft";
import { DiuDossier } from "@/components/dossier/DiuDossier";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { can } from "@/lib/plan";
import { ProsumatorQuickForm } from "@/components/dossier/ProsumatorQuickForm";
import { AtrQuickForm } from "@/components/dossier/AtrQuickForm";
import { DiuQuickForm } from "@/components/dossier/DiuQuickForm";

function installedPanelKwp(pros) {
  if (!pros) return "";
  const number = (value) => {
    const parsed = Number(String(value ?? "").replace(",", "."));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const inverters = pros.cef?.inverters || [];
  const calculated = inverters.reduce((total, inverter) => {
    const panelW = number(inverter.panel_w);
    const panels = (inverter.strings || []).reduce((sum, string) => sum + number(string.panels), 0);
    const count = Math.max(1, number(inverter.count || inverter.quantity) || 1);
    return total + panels * panelW * count / 1000;
  }, 0);
  if (calculated > 0) return Number(calculated.toFixed(3));
  const legacyPanels = number(pros.panel_count);
  const legacyW = number(pros.panel_w);
  if (legacyPanels > 0 && legacyW > 0) return Number((legacyPanels * legacyW / 1000).toFixed(3));
  return pros.cef?.total_kwp || pros.panel_kwp || pros._kwp || "";
}

function normalizeClientName(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
}

function Field({ f, value, onChange, refOptions, ai }) {
  if (f.type === "section") return <h3 className="sm:col-span-2 mt-3 pt-3 border-t text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)", borderColor: "var(--line)" }}>{f.label}</h3>;
  const common = { className: "den-input", value: value ?? "", onChange: (e) => onChange(f.name, e.target.value), placeholder: f.placeholder || "", "data-testid": `field-${f.name}` };
  return (
    <div className={`den-field ${f.full ? "sm:col-span-2" : ""}`}>
      <label>{f.label}</label>
      {f.type === "textarea" ? (
        <><textarea {...common} rows={3} />{ai && <AiDraft module={ai.module} field={f.name} label={f.label} form={ai.form} onApply={onChange} />}</>
      ) : f.type === "select" ? (
        <select {...common}><option value="">Alege...</option>{value && !f.options.includes(value) && <option value={value}>{value}</option>}{f.options.map((o) => <option key={o} value={o}>{o}</option>)}</select>
      ) : f.type === "ref" ? (
        <select {...common}><option value="">Alege...</option>{value && !(refOptions[f.ref] || []).some((o) => o.label === value) && <option value={value}>{value} (nou)</option>}{(refOptions[f.ref] || []).map((o) => <option key={o.id} value={o.label}>{o.label}</option>)}</select>
      ) : (
        <input {...common} type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} step={f.type === "number" ? "any" : undefined} />
      )}
    </div>
  );
}

export default function ModulePage({ moduleKey }) {
  const params = useParams();
  const key = moduleKey || params.module;
  const cfg = MODULES[key];
  const { user } = useAuth();
  const role = user?.role || "admin";
  const canDelete = role === "admin" || (role !== "limitat" && !["prosumator", "clients"].includes(key));
  const [items, setItems] = useState([]);
  const [linkedProsumer, setLinkedProsumer] = useState([]);
  const [linkedDiu, setLinkedDiu] = useState([]);
  const [showTestRecords, setShowTestRecords] = useState(() => new URLSearchParams(window.location.search).get("showTests") === "1");
  const [creatingTestDossier, setCreatingTestDossier] = useState(false);
  const [form, setForm] = useState(null); // null=hidden, {} = open
  const [editId, setEditId] = useState(null);
  const [checks, setChecks] = useState({});
  const [refOptions, setRefOptions] = useState({});
  const [q, setQ] = useState("");
  const [savedAt, setSavedAt] = useState(0);
  const [diuPre, setDiuPre] = useState(false);
  const [catalogImportsBusy, setCatalogImportsBusy] = useState(false);

  const load = () => api.get(`/data/${key}`).then((r) => {
    setItems(r.data);
    const eid = new URLSearchParams(window.location.search).get("edit");
    const it = eid && r.data.find((x) => x.id === eid);
    if (it) { setForm({ ...it }); setEditId(it.id); setChecks(it.checklist || {}); window.history.replaceState(null, "", window.location.pathname); }
  }).catch(() => {});

  useEffect(() => {
    setForm(null); setEditId(null); setChecks({}); setQ("");
    load();
    const refs = [...new Set((cfg.fields || []).filter((f) => f.type === "ref").map((f) => f.ref))];
    refs.forEach((ref) => {
      api.get(`/data/${ref}`).then((r) => {
        const showTestRecords = new URLSearchParams(window.location.search).get("showTests") === "1";
        const rows = ref === "clients" && !showTestRecords ? r.data.filter((item) => !/\bTEST\b/i.test(String(item.name || ""))) : r.data;
        setRefOptions((prev) => ({ ...prev, [ref]: rows.map((x) => ({ ...x, id: x.id, label: MODULES[ref].display(x) })) }));
      }).catch(() => {});
    });
    if (key === "atr") api.get("/data/prosumator").then((r) => setRefOptions((prev) => ({ ...prev, prosumator: r.data || [] }))).catch(() => {});
    if (key === "atr") {
      const params = new URLSearchParams(window.location.search);
      const clientId = params.get("clientId");
      if (params.get("new") === "atr" && !clientId) {
        setForm({ date: new Date().toISOString().slice(0, 10), submission_mode: "Solicitantul depune direct" });
        setEditId(null);
        setChecks({});
        window.history.replaceState(null, "", window.location.pathname);
      }
      if (params.get("new") === "atr" && clientId) {
        Promise.all([api.get("/data/clients"), api.get("/data/prosumator")]).then(([clientsRes, prosRes]) => {
          const client = (clientsRes.data || []).find((item) => item.id === clientId);
          const linkedPros = (prosRes.data || []).filter((item) => item.client_id ? item.client_id === clientId : Boolean(client && normalizeClientName(item.client_name) === normalizeClientName(client.name)));
          const requestedProsId = params.get("prosId");
          const pros = requestedProsId
            ? linkedPros.find((item) => item.id === requestedProsId)
            : linkedPros.length === 1 ? linkedPros[0] : null;
          if (!client) return;
          const kind = String(client.kind || "").toLowerCase();
          const caseName = params.get("case") || "";
          const requestType = caseName.toLocaleLowerCase("ro-RO").includes("spor")
            ? "dezvoltarea unui utilizator existent (spor de putere)"
            : "";
          setForm({
            date: new Date().toISOString().slice(0, 10),
            submission_mode: "Solicitantul depune direct",
            client_name: MODULES.clients.display(client),
            client_id: client.id,
            ...(pros ? { pros_id: pros.id, kind: "Loc de consum și de producere (prosumator)",
              supply: pros.supply || "", p_abs_kw: pros.bransament_kw || "",
              pv_kw: installedPanelKwp(pros), p_evac_kw: pros.power || "" } : {}),
            applicant_type: /jurid/.test(kind) ? "Persoană juridică" : /fiz|persoan/.test(kind) ? "Persoană fizică" : "",
            pod: client.pod || pros?.pod || "",
            operator: client.operator || pros?.operator || "",
            address: client.address || pros?.address || "",
            cf_nr: client.cf_nr || pros?.cf_nr || "",
            cadastral_nr: client.cadastral_nr || pros?.cadastral_nr || "",
            request_type: requestType,
            ...(caseName ? { deer_case: caseName } : {}),
          });
          setEditId(null); setChecks({});
          window.history.replaceState(null, "", window.location.pathname);
        }).catch(() => {});
      }
    }
    if (key === "clients" || key === "prosumator" || key === "atr") {
      api.get("/data/prosumator").then((r) => setLinkedProsumer(r.data || [])).catch(() => {});
      if (key !== "atr") api.get("/data/diu").then((r) => setLinkedDiu(r.data || [])).catch(() => {});
    }
    if (key === "diu") {
      const params = new URLSearchParams(window.location.search);
      const clientId = params.get("clientId");
      const prosId = params.get("prosId");
      if (params.get("new") === "diu" && clientId) {
        Promise.all([api.get("/data/clients"), prosId ? api.get("/data/prosumator") : Promise.resolve({ data: [] })]).then(([clientsRes, prosRes]) => {
          let client = (clientsRes.data || []).find((item) => item.id === clientId);
          const linkedPros = (prosRes.data || []).filter((item) => item.client_id ? item.client_id === clientId : Boolean(client && normalizeClientName(item.client_name) === normalizeClientName(client.name)));
          const pros = prosId
            ? linkedPros.find((item) => item.id === prosId)
            : linkedPros.length === 1 ? linkedPros[0] : null;
          const showTests = params.get("showTests") === "1";
          if (!client && showTests && (pros?.is_test || /\bTEST\b/i.test(String(pros?.client_name || "")))) {
            client = { id: clientId, name: pros.client_name || "TEST — client demonstrativ", address: pros.address || "", operator: pros.operator || "" };
            setRefOptions((prev) => {
              const clients = prev.clients || [];
              return clients.some((item) => item.id === clientId)
                ? prev
                : { ...prev, clients: [...clients, { ...client, label: MODULES.clients.display(client) }] };
            });
          }
          if (!client) return;
          const grid = pros?.cef?.grid || {};
          const hasStorage = Boolean(pros && (pros.battery || /hibrid/i.test(String(pros.system_type || ""))
            || (pros.cef?.shared_batteries || []).length
            || (pros.cef?.inverters || []).some((inv) => inv.battery_mode === "own" ? Boolean(inv.battery?.model) : inv.battery_mode === "shared" && Boolean(inv.shared_battery_id))));
          const circuits = (pros?.cef?.inverters || []).map((inv, index) => {
            const ac = inv.ac || {};
            const count = Math.max(1, Number(inv.count) || 1);
            return { name: `INV${index + 1} — ${inv.brand_model || "invertor"}${count > 1 ? ` × ${count} buc.` : ""}`,
              breaker_a: ac.breaker_a || "", curve: ac.curve || "C", section: ac.section || "", cable: ac.cable_type || "",
              length: ac.length_m || "", rcd_ma: inv.rcd_ma || "", rcd_type: inv.rcd_type || "" };
          });
          setForm({
            client_name: pros?.client_name || client.name || "",
            client_id: client.id,
            ...(pros ? { pros_id: pros.id, circuits } : {}),
            address: pros?.address || client.address || "",
            operator: pros?.operator || client.operator || "",
            power: pros?.inverter_kw || pros?.power || "",
            atr: pros?.atr || "",
            type: pros ? (hasStorage ? "Sistem fotovoltaic hibrid" : "Sistem fotovoltaic on-grid") : "",
            supply: pros?.supply || "",
            earthing: grid.earthing || "",
            bmp_a: grid.bmp_a || "",
            tg_breaker_a: grid.tg_breaker_a || "",
            status: "În lucru",
          });
          setEditId(null);
          setChecks({});
          window.history.replaceState(null, "", window.location.pathname);
        }).catch(() => {});
      }
    }
    // eslint-disable-next-line
  }, [key]);

  const openNew = () => { setForm(key === "atr" ? { date: new Date().toISOString().slice(0, 10), submission_mode: "Solicitantul depune direct" } : {}); setEditId(null); setChecks({}); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); };
  const setVal = (name, value) => {
    if (key === "atr" && name === "client_name") {
      const client = (refOptions.clients || []).find((c) => c.label === value);
      if (!client) {
        setForm((p) => ({ ...p, client_name: value, client_id: "", pros_id: "", pod: "", operator: "", address: "",
          cf_nr: "", cadastral_nr: "", kind: "", supply: "", p_abs_kw: "", pv_kw: "", p_evac_kw: "", request_type: "", deer_case: "" }));
        return;
      }
      const normalize = (v) => String(v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
      const linkedPros = (refOptions.prosumator || []).filter((p) => {
        if (p.client_id) return p.client_id === client.id;
        const pName = normalize(p.client_name);
        return [client.name, client.label].some((name) => pName && pName === normalize(name));
      });
      const linked = linkedPros.length === 1 ? linkedPros[0] : null;
      const clientKind = String(client.kind || "").toLowerCase();
      const applicantType = /jurid/.test(clientKind) ? "Persoană juridică" : /fiz|persoan/.test(clientKind) ? "Persoană fizică" : "";
      const next = {
        client_name: value, client_id: client.id,
        pod: client.pod || linked?.pod || "",
        operator: client.operator || linked?.operator || "",
        address: client.address || linked?.address || "",
        cf_nr: client.cf_nr || linked?.cf_nr || "",
        cadastral_nr: client.cadastral_nr || linked?.cadastral_nr || "",
        applicant_type: applicantType,
        pros_id: linked?.id || "",
        kind: "", supply: "", p_abs_kw: "", pv_kw: "", p_evac_kw: "", request_type: "", deer_case: "",
      };
      if (linked) {
        next.kind = "Loc de consum și de producere (prosumator)";
        if (linked.supply) next.supply = linked.supply;
        if (linked.bransament_kw) next.p_abs_kw = linked.bransament_kw;
        const installedKwp = installedPanelKwp(linked);
        if (installedKwp) next.pv_kw = installedKwp;
        if (linked.power) next.p_evac_kw = linked.power;
        if (/spor/i.test(String(linked.request_type || ""))) {
          next.request_type = "dezvoltarea unui utilizator existent (spor de putere)";
          next.deer_case = "Loc existent — spor de putere — Anexa 1";
        }
      }
      setForm((p) => ({ ...p, ...next }));
      return;
    }
    if (key === "atr" && name === "deer_case") {
      const mappedRequest = {
        "Loc nou de consum și producere — Anexa 1": "utilizator nou definitiv",
        "Loc existent — notificare — Anexa 2": "modificarea elementelor de natură tehnică fără depășirea puterii aprobate anterior",
        "Loc existent prosumator — actualizare CRR — Anexa 3": "modificarea elementelor de natură administrativă fără depășirea puterii aprobate anterior",
        "Loc existent — spor de putere — Anexa 1": "dezvoltarea unui utilizator existent (spor de putere)",
        "Prosumator prin program de finanțare — Anexa 4": "utilizator nou definitiv",
        "Loc existent ≤10,8 kW — notificare simplificată — Anexa 5": "modificarea elementelor de natură tehnică fără depășirea puterii aprobate anterior",
      }[value];
      setForm((p) => ({ ...p, deer_case: value, ...(mappedRequest ? { request_type: mappedRequest } : {}) }));
      return;
    }
    if (key === "atr" && name === "pod") {
      const pod = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
      let detected = "";
      let note = "";
      if (/^RO001E/.test(pod)) detected = "Rețele Electrice Muntenia S.A.";
      else if (/^RO002E/.test(pod)) detected = "Rețele Electrice Dobrogea S.A.";
      else if (/^RO005E/.test(pod)) detected = "Rețele Electrice Banat S.A.";
      else if (/^EMO3/.test(pod)) detected = "Delgaz Grid S.A.";
      else if (/^5940\d{14}$/.test(pod)) {
        detected = "DEER — sucursală de confirmat";
        note = "POD-ul indică DEER; sucursala trebuie confirmată după județ/localitate.";
      } else if (pod) {
        note = "Nu am putut identifica în siguranță operatorul din prefixul POD. Verifică operatorul pe factura de energie sau în instrumentul ANRE.";
      }
      setForm((p) => ({ ...p, pod, ...(detected ? { operator: detected } : {}), pod_check_note: note }));
      return;
    }
    setForm((p) => ({ ...p, [name]: value }));
  };

  const save = async () => {
    if (key === "prosumator" && catalogImportsBusy) {
      toast.warning("Așteaptă să se termine preluarea fișelor și certificatelor din catalog.");
      return;
    }
    const orig = items.find((i) => i.id === editId);
    if (key === "diu" && editId && form.status === "Predat beneficiarului" && orig?.status !== "Predat beneficiarului" && can(user, "ai_gpt")) { setDiuPre(true); return; }
    return doSave().catch(() => {});
  };
  const doSave = async () => {
    const required = (cfg.fields || []).filter((f) => f.required);
    for (const f of required) { if (!form[f.name]) { toast.error(`Completează: ${f.label.replace(" *", "")}`); return; } }
    if (key === "atr" && /deer|distribuție energie electrică|distributie energie electrica/i.test(String(form.operator || "")) && !form.deer_case) { toast.error("Alege procedura DEER aplicabilă"); return; }
    const payload = { ...form };
    if (cfg.checklist) payload.checklist = checks;
    try {
      let savedId = editId;
      if (editId) await api.put("/data/" + key + "/" + editId, payload);
      else if (key === "prosumator") await api.post("/import/prosumator", payload);
      else {
        const { data } = await api.post("/data/" + key, payload);
        savedId = data?.id || null;
      }
      let importFailed = false;
      if (!editId && key === "diu" && payload.pros_id && savedId) {
        try { await api.post("/diu/" + encodeURIComponent(savedId) + "/import-pros", { pros_id: payload.pros_id }); }
        catch { importFailed = true; }
      }
      if (importFailed) toast.warning("DI-U creat; nu s-au putut prelua automat toate datele din dosarul prosumator.");
      else toast.success("Salvat cu succes");
      if (key === "diu" && editId) { setSavedAt(Date.now()); load(); return; }
      setForm(null); setEditId(null); setChecks({}); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eroare la salvare"); throw e; }
  };

  const createTestDossier = async () => {
    if (creatingTestDossier || hiddenTestCount > 0) return;
    setCreatingTestDossier(true);
    try {
      const { data } = await api.post("/test-dossier");
      setShowTestRecords(true);
      await load();
      toast.success(`Dosar demonstrativ TEST creat: ${data?.number || "gata"}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Nu s-a putut crea dosarul demonstrativ TEST");
    } finally {
      setCreatingTestDossier(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Ștergi această înregistrare?")) return;
    await api.delete(`/data/${key}/${id}`);
    toast.success("Șters"); load();
  };

  const isTestRecord = (item) => /\bTEST\b/i.test([item.number, item.name, item.client_name, item.idcode].filter(Boolean).join(" "));
  const hiddenTestCount = ["clients", "prosumator", "diu"].includes(key) ? items.filter(isTestRecord).length : 0;
  const onlyTestRecords = items.length > 0 && items.every(isTestRecord);
  const visibleItems = showTestRecords === true ? items : (["clients", "prosumator", "diu"].includes(key) ? items.filter((item) => !isTestRecord(item)) : items);
  const showTestDossiers = () => {
    setQ("");
    setShowTestRecords(true);
    window.setTimeout(() => document.querySelector('[data-testid="saved-records"]')?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  };
  const filtered = useMemo(() => {
    if (!q) return visibleItems;
    const ql = q.toLowerCase();
    return visibleItems.filter((i) => JSON.stringify(i).toLowerCase().includes(ql));
  }, [visibleItems, q]);

  const checkedCount = cfg.checklist ? cfg.checklist.filter((c) => checks[c]).length : 0;

  return (
    <div>
      <PageHeader eyebrow={cfg.eyebrow} title={cfg.title} sub={cfg.sub}
        action={<div className="flex gap-2 flex-wrap">
          {form ? <Btn data-testid="add-btn" onClick={() => setForm(null)}><X size={15} /> Închide</Btn> : key === "atr"
            ? <a data-testid="add-btn" href="/cerere-atr?new=atr" className="inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold text-white shadow-[0_4px_12px_#2878f022]" style={{ background: "var(--blue)" }}><Plus size={15} /> {cfg.addLabel}</a>
            : <Btn data-testid="add-btn" onClick={openNew}><Plus size={15} /> {cfg.addLabel}</Btn>}
        </div>} />

      {key === "atr" && <section className="mb-6 overflow-hidden rounded-2xl border shadow-sm" aria-label="Flux cerere ATR" data-testid="atr-workflow" style={{ borderColor: "var(--line)", background: "#fff" }}>
        <div className="grid lg:grid-cols-[1.35fr_1fr]">
          <div className="p-5 sm:p-7 lg:p-8" style={{ background: "linear-gradient(135deg, #f0f6ff 0%, #ffffff 72%)" }}>
            <div className="text-[11px] font-bold uppercase tracking-[.16em]" style={{ color: "var(--blue)" }}>Flux de lucru · ATR</div>
            <h2 className="mt-2 max-w-2xl text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: "#13243d" }}>Cererea pornește din datele clientului</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--muted)" }}>Alege clientul și dosarul prosumator asociat. Datele cunoscute, puterile și echipamentele se preiau automat; verifică procedura și valorile înainte de generare.</p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <a href="/cerere-atr?new=atr" data-testid="atr-start-new" className="inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold text-white text-white shadow-[0_4px_12px_#2878f022]" style={{ background: "var(--blue)" }}><Plus size={15} /> Cerere ATR nouă</a>
              <a href="/clienti" className="inline-flex min-h-10 items-center rounded-lg border bg-white px-4 text-sm font-semibold" style={{ borderColor: "var(--line)", color: "#31425c" }}>Alege din clienți</a>
            </div>
            <p className="mt-3 text-xs leading-5" style={{ color: "var(--muted)" }}>Pachetul ATR include formularul de lucru și anexele oficiale disponibile pentru operatorul selectat. Formularele PDF oficiale se păstrează ca surse; verifică cerințele operatorului înainte de depunere.</p>
          </div>
          <div className="border-t p-5 sm:p-7 lg:border-l lg:border-t-0" style={{ borderColor: "var(--line)", background: "#fbfcfe" }}>
            <div className="text-[11px] font-bold uppercase tracking-[.16em]" style={{ color: "var(--muted)" }}>Pașii dosarului</div>
            <ol className="mt-4 grid gap-2">
              {[
                ["01", "Client și loc de consum", "CI, adresă, POD și operator"],
                ["02", "Tipul solicitării", "ATR nou, spor sau modificare"],
                ["03", "Instalația", "Preia invertorul, panourile și bateria"],
                ["04", "Documente", "Descarcă cererea, anexele și schema separat"],
              ].map(([n, title, body]) => <li key={n} className="flex gap-3 rounded-xl px-3 py-3" style={{ background: "#fff" }}>
                <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold" style={{ background: "#eaf1ff", color: "var(--blue)" }}>{n}</span>
                <span><b className="block text-sm">{title}</b><span className="mt-1 block text-xs leading-5" style={{ color: "var(--muted)" }}>{body}</span></span>
              </li>)}
            </ol>
            <a href="/formulare-oficiale" className="mt-4 inline-flex text-xs font-semibold" style={{ color: "var(--blue)" }}>Deschide formularele oficiale →</a>
          </div>
        </div>
      </section>}

      {key === "prosumator" && <section className="mb-6 overflow-hidden rounded-2xl border shadow-sm" aria-label="Flux dosar prosumator" data-testid="prosumer-workflow" style={{ borderColor: "var(--line)", background: "#fff" }}>
        <div className="grid lg:grid-cols-[1.35fr_1fr]">
          <div className="p-5 sm:p-7 lg:p-8" style={{ background: "linear-gradient(135deg, #f0f6ff 0%, #ffffff 72%)" }}>
            <div className="text-[11px] font-bold uppercase tracking-[.16em]" style={{ color: "var(--blue)" }}>Dosar nou · prosumator</div>
            <h2 className="mt-2 max-w-2xl text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: "#13243d" }}>Pornește din actele clientului</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--muted)" }}>Încarcă CI, factura și cartea funciară. Aplicația extrage datele disponibile, le salvează la client și deschide dosarul pentru verificare.</p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <DossierDocumentStart onCreated={(data) => { setForm({ ...data }); setEditId(data.id); setChecks(data.checklist || {}); load(); }} />
              <Btn variant="secondary" onClick={openNew} data-testid="prosumer-manual-start"><Plus size={15} /> Introducere manuală</Btn>
            </div>
            <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>Datele extrase rămân de verificat. Sistemul nu completează măsurători reale în locul instalatorului.</p>
            {key === "prosumator" && hiddenTestCount > 0 && <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-dashed p-3" style={{ borderColor: "var(--line)", background: "#fff" }}>
              <Btn variant="secondary" onClick={showTestDossiers} data-testid="show-test-dossiers">Deschide dosarele demonstrative ({hiddenTestCount})</Btn>
              <span className="text-xs leading-5" style={{ color: "var(--muted)" }}>Înregistrări sintetice TEST, marcate separat; le poți folosi pentru a vedea dosarul, schema și documentele generate.</span>
            </div>}
            {role === "admin" && hiddenTestCount === 0 && <div className="mt-4 rounded-xl border border-dashed p-3" style={{ borderColor: "var(--line)", background: "#fff" }}>
              <div className="flex flex-wrap items-center gap-3">
                <Btn variant="secondary" onClick={createTestDossier} disabled={creatingTestDossier} data-testid="create-test-dossier">
                  {creatingTestDossier ? "Se pregătește dosarul..." : "Creează dosar demonstrativ TEST"}
                </Btn>
                <span className="text-xs leading-5" style={{ color: "var(--muted)" }}>Date sintetice marcate TEST, doar pentru verificarea fluxului. Nu sunt acte sau măsurători reale și nu se depun.</span>
              </div>
            </div>}
          </div>
          <div className="border-t p-5 sm:p-7 lg:border-l lg:border-t-0" style={{ borderColor: "var(--line)", background: "#fbfcfe" }}>
            <div className="text-[11px] font-bold uppercase tracking-[.16em]" style={{ color: "var(--muted)" }}>Continuă un dosar</div>
            <h3 className="mt-2 text-lg font-bold" style={{ color: "#13243d" }}>Acces direct la următorul pas</h3>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[["/cerere-atr", "Cerere ATR"], ["/spor-putere", "Spor de putere"], ["/diu", "Dosar DI-U"], ["/catalog-echipamente", "Catalog echipamente"]].map(([href, label]) =>
                <a key={href} href={href} className="flex min-h-11 items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-xs font-bold hover:border-blue-400" style={{ borderColor: "var(--line)", color: "#31425c" }}>
                  {label}<span aria-hidden="true" style={{ color: "var(--blue)" }}>›</span>
                </a>)}
            </div>
            <p className="mt-4 text-xs leading-5" style={{ color: "var(--muted)" }}>Alege clientul din formular pentru preluarea automată a datelor cunoscute în ATR, spor sau DI-U.</p>
          </div>
        </div>
        <div className="border-t px-5 py-4 sm:px-7" style={{ borderColor: "var(--line)" }}>
          <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["01", "Documente client", "CI → factură → carte funciară. Verifică datele citite."],
              ["02", "Instalație", "Selectează echipamentele și confirmă datele locului de consum."],
              ["03", "Control tehnic", "Verifică dimensionarea, protecțiile, cablurile și schema."],
              ["04", "Depunere", "Descarcă separat dosarul, schema, PRAM și documentele PIF."],
            ].map(([n, title, body]) => <li key={n} className="flex gap-3 rounded-xl px-3 py-3" style={{ background: "#f8fafd" }}>
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold" style={{ background: "#eaf1ff", color: "var(--blue)" }}>{n}</span>
              <span><b className="block text-sm">{title}</b><span className="mt-1 block text-xs leading-5" style={{ color: "var(--muted)" }}>{body}</span></span>
            </li>)}
          </ol>
        </div>
      </section>}

      {form && (
        <div className="den-panel mb-6" data-testid="module-form">
          <h2 className="text-lg font-bold mb-5">{editId ? "Editează înregistrarea" : cfg.addLabel}</h2>
          {key === "prosumator" ? <ProsumatorQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} onImportsBusyChange={setCatalogImportsBusy} /> : key === "atr" ? <AtrQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : key === "diu" ? <DiuQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : (
            <div className="grid sm:grid-cols-2 gap-4">
              {cfg.fields.map((f, i) => <Field key={f.name || `s${i}`} f={f} value={form[f.name]} onChange={(name, value) => setVal(name, value)} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} />)}
            </div>
          )}
          {key === "atr" && form.pod_check_note && <div className="mt-3 rounded-lg border px-3 py-2 text-sm" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>{form.pod_check_note}</div>}

          {cfg.checklist && key !== "prosumator" && (
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

          {key === "prosumator" && <details className="mt-5 rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
            <summary className="cursor-pointer text-sm font-bold">Avansat: dimensionare, schemă și documente</summary>
            <div className="mt-4 space-y-4">
              <AssignBox value={form.assigned_to} onChange={(v) => setVal("assigned_to", v)} />
              <CefEditor value={form.cef} onChange={(v) => setVal("cef", v)} />
              {editId && <SldPanel id={editId} form={form} setVal={setVal} />}
              <DossierExtras form={form} setVal={setVal} />
              {editId && <DossierOpis id={editId} />}
              {editId && <SimpleDossierBtn id={editId} />}
              {editId && <PifPanel id={editId} />}
              {editId && <AiDossierCheck id={editId} />}
              {editId && <SignRequests dossierId={editId} />}
              <GeneratedDocs id={editId} files={form.files} form={form} />
            </div>
          </details>}
          {key === "power" && <PowerDossier id={editId} form={form} setVal={setVal} />}
          {key === "atr" && <AtrDossier id={editId} form={form} setVal={setVal} clients={refOptions.clients || []} />}
          {key === "diu" && <DossierExtras form={form} setVal={setVal} compact />}
          {key === "diu" && editId && <DiuDossier id={editId} form={form} setVal={setVal} setForm={setForm} savedAt={savedAt} />}
          {key === "diu" && editId && <SignRequests dossierId={editId} module="diu" />}
          {key === "diu" && editId && <AiPrecheck id={editId} base="diu" open={diuPre} onClose={() => setDiuPre(false)} onFinalize={doSave} form={form}
            title="Verificare AI înainte de predarea către beneficiar" action="Salvează ca „Predat beneficiarului”" />}
          {(key === "power" || key === "atr") && editId && <AiRacordCheck id={editId} module={key} />}
          {["prosumator", "diu", "power", "atr"].includes(key) && editId && <AiOdReview id={editId} module={key} />}
          {key === "clients" && editId && <ClientDocs client={form} onChange={(docs) => setVal("docs", docs)} />}
          {key === "clients" && editId && <SignRequests clientName={form.name} />}

          <div className="flex gap-2 mt-6 den-noprint">
            <Btn onClick={save} disabled={key === "prosumator" && catalogImportsBusy} data-testid="save-btn">{catalogImportsBusy ? "Se preiau documentele…" : "Salvează"}</Btn>
            <Btn variant="secondary" onClick={() => window.print()} data-testid="pdf-btn">Tipărește / PDF</Btn>
            <Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>
          </div>
        </div>
      )}

      <div className="den-panel" data-testid="saved-records">
        {onlyTestRecords && showTestRecords === true && <div className="mb-4 rounded-lg border px-3 py-2 text-xs font-medium" style={{ borderColor: "#f2d28c", background: "#fff9e9", color: "#73520b" }} role="status">Sunt afișate dosare demonstrative marcate TEST. Folosește-le numai pentru verificarea fluxului; nu conțin date reale și nu se depun.</div>}
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <h2 className="text-lg font-bold">Înregistrări salvate <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({visibleItems.length})</span></h2>
          {hiddenTestCount > 0 && <button type="button" className="text-xs underline" onClick={() => setShowTestRecords((value) => !value)}>{showTestRecords === true ? "Ascunde" : "Arată"} înregistrările TEST ({hiddenTestCount})</button>}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input data-testid="search-input" className="den-input w-[240px]" style={{ paddingLeft: 34 }} placeholder="Caută..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu există înregistrări încă.</div>
        ) : (
          <>
          {key === "clients" && <div className="grid gap-3 sm:hidden" data-testid="mobile-client-actions">
            {filtered.map((it) => {
              const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
              const prosList = linkedProsumer.filter((p) => p.client_id ? p.client_id === it.id : normalize(p.client_name) === normalize(it.name));
              const pros = prosList.length === 1 ? prosList[0] : null;
              const diuList = linkedDiu.filter((d) => (d.client_id ? d.client_id === it.id : normalize(d.client_name) === normalize(it.name)) || (d.pros_id && d.pros_id === pros?.id));
              const diu = diuList.length === 1 ? diuList[0] : null;
              const base = "/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (pros ? "&prosId=" + encodeURIComponent(pros.id) : "");
              const actionClass = "inline-flex min-h-9 items-center justify-center rounded-lg border px-3 py-2 text-xs font-semibold";
              return <article key={it.id} className="rounded-xl border p-4 shadow-sm" style={{ borderColor: "var(--line)", background: "#fff" }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-bold">{it.name || "Client"}</h3>
                    <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>{[it.address, it.locality, it.county].filter(Boolean).join(", ") || "Adresă loc de consum necompletată"}</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>POD: {it.pod || "—"} · {it.operator || "Operator neales"}</p>
                  </div>
                  <button type="button" className="shrink-0 rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openEdit(it)}>Editează</button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a className={actionClass} style={{ color: "var(--blue)", borderColor: "var(--line)" }} href={base}>Cerere ATR</a>
                  <a className={actionClass} style={{ color: "var(--blue)", borderColor: "var(--line)" }} href={base + "&case=" + encodeURIComponent("Loc existent — spor de putere — Anexa 1")}>Spor de putere</a>
                  <a className={actionClass} style={{ color: "var(--blue)", borderColor: "var(--line)" }} href={"/diu?new=diu&clientId=" + encodeURIComponent(it.id) + (pros ? "&prosId=" + encodeURIComponent(pros.id) : "")}>Creează DI-U</a>
                </div>
                {(pros || diu) && <details className="mt-3 border-t pt-3" style={{ borderColor: "var(--line)" }}>
                  <summary className="cursor-pointer text-xs font-semibold" style={{ color: "var(--blue)" }}>Descarcă documentele disponibile</summary>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {pros && <>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile("/dossier/" + pros.id + "/export")}>Dosar prosumator</button>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/sld/" + pros.id + "/pdf", "schema_monofilara_" + pros.id.slice(0, 8) + ".pdf")}>Schema monofilara</button>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/dossier/" + pros.id + "/file/priza", "pram_priza_" + pros.id.slice(0, 8) + ".pdf")}>Buletin PRAM</button>
                    </>}
                    {diu && <>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/diu/" + diu.id + "/pdf?doc=pram_priza", "pram_priza_diu_" + diu.id.slice(0, 8) + ".pdf")}>PRAM priză DI-U</button>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/diu/" + diu.id + "/pdf?doc=pram_cont", "pram_continuitate_" + diu.id.slice(0, 8) + ".pdf")}>Continuitate DI-U</button>
                    </>}
                  </div>
                </details>}
                {prosList.length > 1 && <p className="mt-2 text-xs text-amber-700">Există mai multe dosare prosumator; deschide-l pe cel potrivit din lista de dosare.</p>}
                {diuList.length > 1 && <p className="mt-1 text-xs text-amber-700">Există mai multe dosare DI-U pentru acest client.</p>}
              </article>;
            })}
          </div>}
          {key === "prosumator" && <div className="grid gap-3 sm:hidden" data-testid="mobile-prosumer-actions">
            {filtered.map((it) => {
              const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\\s+/g, " ");
              const diu = linkedDiu.find((d) => d.pros_id === it.id || (d.client_id ? d.client_id === it.client_id : normalize(d.client_name) === normalize(it.client_name)));
              const actionClass = "inline-flex min-h-9 items-center justify-center rounded-lg border px-3 py-2 text-xs font-semibold";
              return <article key={it.id} className="rounded-xl border p-4 shadow-sm" style={{ borderColor: "var(--line)", background: "#fff" }} data-testid={`prosumer-card-${it.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-bold">{it.client_name || it.number || "Dosar prosumator"}</h3>
                    <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>{it.number || "Fără număr"} · {it.power || it._kwp || "Putere necompletată"} kW</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{it.operator || "Operator neales"} · {it.status || "În lucru"}</p>
                  </div>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => openEdit(it)}>Deschide</button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/export`)}>Dosar PDF</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/sld/${it.id}/pdf`, `schema_monofilara_${it.id.slice(0, 8)}.pdf`)}>Schema</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/dossier/${it.id}/file/priza`, `pram_priza_${it.id.slice(0, 8)}.pdf`)}>PRAM priză</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/dossier/${it.id}/pif/pdf`, `pif_${it.id.slice(0, 8)}.pdf`)}>Proces verbal PIF</button>
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}`}>Cerere ATR</a>}
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}&case=${encodeURIComponent("Loc existent — spor de putere — Anexa 1")}`}>Spor de putere</a>}
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/diu?new=diu&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}`}>Creează DI-U</a>}
                  {diu && <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`, `pram_priza_diu_${diu.id.slice(0, 8)}.pdf`)}>PRAM DI-U</button>}
                </div>
              </article>;
            })}
          </div>}
          {key === "atr" && <div className="grid gap-3 sm:hidden" data-testid="atr-mobile-cards">
            {filtered.map((it) => {
              const linked = linkedProsumer.find((p) => it.pros_id
                ? p.id === it.pros_id && (!it.client_id || !p.client_id || p.client_id === it.client_id)
                : Boolean(it.client_id && p.client_id === it.client_id && it.pod && p.pod === it.pod));
              const isDeer = /deer|distributie energie electrica romania/i.test(String(it.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""));
              return <article key={it.id} className="rounded-xl border bg-white p-4 shadow-sm" style={{ borderColor: "var(--line)" }} data-testid={`atr-mobile-card-${it.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-bold">{it.client_name || "Solicitant necompletat"}</h3>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{it.operator || "Operator necompletat"}</p>
                  </div>
                  <span className="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold" style={{ background: linked ? "#dcfce7" : "#fff7ed", color: linked ? "#166534" : "#9a6700" }}>{linked ? "Echipamente legate" : "Lipsește dosar PV"}</span>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div><dt style={{ color: "var(--muted)" }}>Procedură</dt><dd className="mt-0.5 font-semibold">{it.deer_case || it.request_type || "De selectat"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>POD</dt><dd className="mt-0.5 font-semibold">{it.pod || "De completat"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>Putere absorbită</dt><dd className="mt-0.5 font-semibold">{it.p_abs_kw ? `${it.p_abs_kw} kW` : "—"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>Echipamente</dt><dd className="mt-0.5 font-semibold">{linked ? [...new Set((linked.cef?.inverters || []).map((item) => item.brand_model).filter(Boolean))].join(", ") || "În dosar" : "Se preiau din dosarul prosumator"}</dd></div>
                </dl>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button type="button" className="min-h-10 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openEdit(it)} data-testid={`edit-mobile-${it.id}`}>Editează cererea</button>
                  <button type="button" className="min-h-10 rounded-lg px-3 text-xs font-semibold text-white" style={{ background: "var(--blue)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/package.zip", "Pachet_ATR.zip")} data-testid={`atr-package-mobile-${it.id}`}>Descarcă dosarul ZIP</button>
                  {isDeer && <button type="button" className="col-span-2 min-h-10 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/official-docx", "Anexa_DEER_completata_" + it.id.slice(0, 8) + ".docx")}>Descarcă Anexa DEER completată</button>}
                </div>
              </article>;
            })}
          </div>}
          <div className={["clients", "prosumator", "atr"].includes(key) ? "hidden overflow-x-auto sm:block" : "overflow-x-auto"}>
            <table className="w-full text-sm" data-testid="items-table">
              <thead>
                <tr className="text-left" style={{ background: "#f8fafd", color: "var(--muted)" }}>
                  {cfg.columns.map((c) => <th key={c.key} className="px-3 py-2.5 font-semibold text-[12px] whitespace-nowrap">{c.label}</th>)}
                  {key === "atr" && <th className="px-3 py-2.5 font-semibold text-[12px] whitespace-nowrap">Procedură și instalație</th>}
                  <th className="px-3 py-2.5 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <tr key={it.id} className="border-t hover:bg-[#fafcff]" style={{ borderColor: "var(--line)" }}>
                    {cfg.columns.map((c) => <td key={c.key} className="px-3 py-3 whitespace-nowrap">{it[c.key] || "—"}</td>)}
                    {key === "atr" && (() => {
                      const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
                      const belongsToAtrClient = (prosumer) => {
                        if (it.client_id && prosumer.client_id) return prosumer.client_id === it.client_id;
                        return normalize(prosumer.client_name) === normalize(it.client_name);
                      };
                      const normalizeLocation = (value) => normalize(value).replace(/[^a-z0-9]/g, "");
                      const exactCandidate = it.pros_id ? linkedProsumer.find((p) => p.id === it.pros_id) : null;
                      const exactLink = exactCandidate && belongsToAtrClient(exactCandidate) ? exactCandidate : null;
                      const candidates = linkedProsumer.filter(belongsToAtrClient);
                      const locationValue = it.pod || it.address;
                      const locationMatches = locationValue ? candidates.filter((p) => (
                        normalizeLocation(it.pod ? p.pod : p.address) === normalizeLocation(locationValue)
                      )) : candidates;
                      const linked = exactLink || (locationMatches.length === 1 ? locationMatches[0] : null);
                      const ambiguous = !exactLink && (locationMatches.length > 1 || (!locationValue && candidates.length > 1));
                      const inverters = linked?.cef?.inverters || [];
                      const panels = [...new Set(inverters.map((x) => x.panel_model).filter(Boolean))];
                      const batteries = [
                        ...inverters.filter((x) => x.battery_mode === "own" && x.battery?.model).map((x) => x.battery.model),
                        ...(linked?.cef?.shared_batteries || []).map((x) => x.model).filter(Boolean),
                      ];
                      const procedure = it.deer_case || (it.operator && /deer|distributie energie electrica/i.test(it.operator) ? "Alege procedura DEER" : "Procedură necompletată");
                      return <td className="px-3 py-3 min-w-[220px] max-w-[340px] whitespace-normal" data-testid={`atr-summary-${it.id}`}>
                        <div className="font-semibold">{procedure}</div>
                        {linked ? <div className="mt-1 text-[11px] leading-5" style={{ color: "var(--muted)" }}>
                          {inverters.length ? `Invertor: ${[...new Set(inverters.map((x) => x.brand_model).filter(Boolean))].join(", ")}` : "Invertor: nepreluat"}
                          {panels.length ? ` · Panouri: ${panels.join(", ")}` : ""}
                          {batteries.length ? ` · Baterie: ${[...new Set(batteries)].join(", ")}` : ""}
                        </div> : <div className="mt-1 text-[11px]" style={{ color: ambiguous ? "#9a6700" : "var(--muted)" }}>{ambiguous ? "Mai multe dosare prosumator — selectează dosarul exact în formularul ATR" : "Fără dosar prosumator asociat"}</div>}
                      </td>;
                    })()}
                    <td className="px-2 py-3 text-left whitespace-normal sticky right-0 z-10 bg-white shadow-[-8px_0_10px_-10px_rgba(15,23,42,0.45)] max-w-[220px]">
                      {key === "clients" && (() => {
                        const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
                        const clientProsumerDossiers = linkedProsumer.filter((p) => p.client_id ? p.client_id === it.id : normalize(p.client_name) === normalize(it.name));
                        const dossier = clientProsumerDossiers.length === 1 ? clientProsumerDossiers[0] : null;
                        const clientDiuDossiers = linkedDiu.filter((d) => (d.client_id ? d.client_id === it.id : normalize(d.client_name) === normalize(it.name)) || (d.pros_id && d.pros_id === dossier?.id));
                        const diu = clientDiuDossiers.length === 1 ? clientDiuDossiers[0] : null;
                        const linkClass = "inline-flex rounded border px-2 py-1 text-[11px] font-semibold mr-1";
                        const diuUrl = "/diu?new=diu&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "");
                        return <span className="inline-flex max-w-[204px] items-center flex-wrap gap-1">
                          <button type="button" className={linkClass} onClick={() => { window.location.href = diuUrl; }}>Creează DI-U</button>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "")}>Cerere ATR</a>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "") + "&case=" + encodeURIComponent("Loc existent — spor de putere — Anexa 1")}>Spor de putere</a>
                          {clientProsumerDossiers.length > 1 && <span className="basis-full text-[10px] text-amber-800">Mai multe dosare PV: selectează-l pe cel corect în ATR / DI-U.</span>}
                          {clientDiuDossiers.length > 1 && <span className="basis-full text-[10px] text-amber-800">Mai multe dosare DI-U: deschide dosarul dorit pentru documente și PRAM.</span>}
                          {dossier && <>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${dossier.id}/export`)}>Dosar PDF</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/sld/${dossier.id}/pdf`, `schema_monofilara_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă schemă</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/dossier/${dossier.id}/pif/pdf`, `pif_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă PIF</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/dossier/${dossier.id}/file/priza`, `pram_priza_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă PRAM</button>
                          </>}
                          {diu && <>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`, `pram_priza_diu_${diu.id.slice(0, 8)}.pdf`)}>Descarcă PRAM priză</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_cont`, `pram_continuitate_${diu.id.slice(0, 8)}.pdf`)}>Descarcă continuitate</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_izol`, `pram_izolatie_${diu.id.slice(0, 8)}.pdf`)}>Descarcă izolație</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_ddr`, `pram_ddr_${diu.id.slice(0, 8)}.pdf`)}>Descarcă DDR</button>
                          </>}
                        </span>;
                      })()}
                      {key === "atr" && <span className="inline-flex items-center flex-wrap gap-1 mr-1"><button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile("/atr/" + it.id + "/pdf?full=0")} title="Descarcă separat cererea ATR în PDF">PDF cerere ATR</button><button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/package.zip", "Pachet_ATR.zip")} title="Pachet ZIP cu PDF-ul ATR și anexa oficială disponibilă pentru operatorul selectat">PDF + anexele disponibile (ZIP)</button>{/deer|distributie energie electrica romania/i.test(String(it.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")) && <button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/official-docx", "Anexa_DEER_completata_" + it.id.slice(0, 8) + ".docx")} title="Descarcă formularul oficial DEER precompletat cu datele cunoscute din dosar">Anexa DEER completată (DOCX)</button>}</span>}
                      {key === "prosumator" && (() => {
                        const token = localStorage.getItem("den_token");
                        const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
                        const diu = linkedDiu.find((d) => d.pros_id === it.id || (d.client_id ? d.client_id === it.client_id : normalize(d.client_name) === normalize(it.client_name)));
                        const linkClass = "inline-flex rounded border px-2 py-1 text-[11px] font-semibold mr-1";
                        const atrUrl = "/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.client_id || "")
                          + "&prosId=" + encodeURIComponent(it.id);
                        const diuUrl = it.client_id ? "/diu?new=diu&clientId=" + encodeURIComponent(it.client_id) + "&prosId=" + encodeURIComponent(it.id) : "";
                        return <span className="inline-flex items-center flex-wrap gap-y-1">
                          {diuUrl && <a className={linkClass} href={diuUrl}>Creează DI-U</a>}
                          {it.client_id && <a className={linkClass} href={atrUrl}>Cerere ATR</a>}
                          {it.client_id && <a className={linkClass} href={atrUrl + "&case=" + encodeURIComponent("Loc existent — spor de putere — Anexa 1")}>Spor de putere</a>}
                          <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/export`)}>Dosar PDF</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/sld/${it.id}/pdf`, `schema_monofilara_${it.id.slice(0, 8)}.pdf`)}>Descarcă schemă</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/dossier/${it.id}/pif/pdf`, `pif_${it.id.slice(0, 8)}.pdf`)}>Descarcă PIF</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/dossier/${it.id}/file/priza`, `pram_priza_${it.id.slice(0, 8)}.pdf`)}>Descarcă PRAM</button>
                          {diu && <>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`, `pram_priza_diu_${diu.id.slice(0, 8)}.pdf`)}>Descarcă PRAM priză</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_cont`, `pram_continuitate_${diu.id.slice(0, 8)}.pdf`)}>Descarcă continuitate</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_izol`, `pram_izolatie_${diu.id.slice(0, 8)}.pdf`)}>Descarcă izolație</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_ddr`, `pram_ddr_${diu.id.slice(0, 8)}.pdf`)}>Descarcă DDR</button>
                          </>}
                        </span>;
                      })()}
                      <button onClick={() => openEdit(it)} data-testid={`edit-${it.id}`} className="p-1.5 rounded hover:bg-[#eef4ff]" title="Editează"><Pencil size={15} style={{ color: "var(--blue)" }} /></button>
                      {canDelete && <button onClick={() => remove(it.id)} data-testid={`delete-${it.id}`} className="p-1.5 rounded hover:bg-[#fff0f0] ml-1" title="Șterge"><Trash2 size={15} style={{ color: "#b33333" }} /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>
    </div>
  );
}
