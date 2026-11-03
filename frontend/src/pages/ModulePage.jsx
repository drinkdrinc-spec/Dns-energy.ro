import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api, API, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";
import { hasConfiguredStorage } from "@/lib/cefStorage";
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

const PROSUMER_OD_STAGES = [
  "Depunerea cererii de racordare",
  "Emiterea avizului tehnic de racordare",
  "Încheierea contractului de racordare și încredințarea execuției lucrării de racordare",
  "Execuția instalației de racordare",
  "Depunerea dosarului instalației electrice interioare",
  "Recepția instalației electrice de racordare",
  "Emiterea certificatului de racordare",
  "Încheierea contractului de furnizare a energiei electrice",
  "Punerea sub tensiune a instalației de utilizare"
];

const PROSUMER_OD_STAGE_GUIDANCE = [
  ["Cererea de racordare", "Actele clientului și ale locului de consum", "Cererea ATR și anexa oficială potrivită operatorului și situației"],
  ["Emiterea avizului", "Avizul tehnic de racordare și condițiile impuse", "Notificările operatorului privind completări sau corecturi"],
  ["Contractul de racordare", "Contractul și documentele de execuție, dacă sunt cerute", "Dovada achitării tarifelor aplicabile"],
  ["Execuția racordării", "Proiectul și documentele lucrării de racordare", "Procesele-verbale și confirmările aferente execuției"],
  ["Dosarul instalației interioare", "DI-U, schema monofilară și documentele echipamentelor", "PRAM, verificări și procese-verbale PIF, după caz"],
  ["Recepția instalației", "Documentele de recepție și rezultatele probelor", "Remedierea și retrimiterea documentelor cerute de operator"],
  ["Certificatul de racordare", "Certificatul emis de operator și condițiile de exploatare", "Verifică puterile și datele tehnice față de dosarul depus"],
  ["Contractul de furnizare", "Contractul cu furnizorul ales", "Confirmarea datelor locului de consum și a titularului"],
  ["Punerea sub tensiune", "Notificarea operatorului și confirmarea stării finale", "Păstrează dovada comunicării și actualizează dosarul ca activ"],
];

const PROSUMER_QUICK_STATUSES = [
  "Dosar în pregătire",
  "Gata de depunere",
  "Depus la operatorul de distribuție",
  "Aviz tehnic emis",
  "Programat pentru montaj",
  "Montaj efectuat",
  "Probe și punere în funcțiune",
  "Prosumator activ",
];

function normalizeClientName(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
}


const CLIENT_SITE_FIELDS = ["address", "county", "locality", "pod", "operator", "supplier", "cf_nr", "cadastral_nr", "nlc"];
function clientConsumptionSites(client) {
  const saved = Array.isArray(client?.consumption_sites)
    ? client.consumption_sites.filter((site) => site && typeof site === "object").map((site, index) => ({ ...site, id: String(site.id || ("saved-" + index)) }))
    : [];
  if (saved.length) return saved;
  if (["address", "pod", "locality", "county"].some((key) => String(client?.[key] || "").trim())) {
    return [{ id: "legacy", ...Object.fromEntries(CLIENT_SITE_FIELDS.map((key) => [key, client?.[key] || ""])) }];
  }
  return [];
}
function clientSiteFor(client, preferredPod) {
  const sites = clientConsumptionSites(client);
  const pod = String(preferredPod || "").replace(/\s+/g, "").toUpperCase();
  return (pod && sites.find((site) => String(site.pod || "").replace(/\s+/g, "").toUpperCase() === pod)) || sites[0] || null;
}
function clientSiteLabel(site, index) {
  return [site.address, site.locality, site.county, site.pod && ("POD " + site.pod)].filter(Boolean).join(" · ") || ("Loc de consum " + (index + 1));
}
function clientSiteMatchesPros(site, pros) {
  if (!site || !pros) return true;
  const sitePod = String(site.pod || "").replace(/\s+/g, "").toUpperCase();
  const prosPod = String(pros.pod || "").replace(/\s+/g, "").toUpperCase();
  if (sitePod && prosPod) return sitePod === prosPod;
  const addressKey = (value) => normalizeClientName(value).replace(/[^a-z0-9]/g, "");
  const siteAddress = addressKey(site.address), prosAddress = addressKey(pros.address);
  return !siteAddress || !prosAddress || siteAddress === prosAddress;
}

function resolveLinkedProsumer(atr, prosumers) {
  const explicit = atr.pros_id ? prosumers.find((prosumer) => prosumer.id === atr.pros_id) : null;
  if (explicit) return { linked: explicit, ambiguous: false };

  const name = normalizeClientName(atr.client_name);
  const sameName = prosumers.filter((prosumer) => name && normalizeClientName(prosumer.client_name) === name);
  const byClient = atr.client_id ? sameName.filter((prosumer) => prosumer.client_id === atr.client_id) : [];
  const hasConflictingClientId = Boolean(atr.client_id && !byClient.length && sameName.some((prosumer) => prosumer.client_id && prosumer.client_id !== atr.client_id));
  const candidates = byClient.length ? byClient : sameName;
  if (candidates.length === 1 && !hasConflictingClientId) return { linked: candidates[0], ambiguous: false };

  const location = atr.pod || atr.address;
  if (location) {
    const normalizeLocation = (value) => normalizeClientName(value).replace(/[^a-z0-9]/g, "");
    const matches = candidates.filter((prosumer) => {
      const candidateLocation = atr.pod ? prosumer.pod : prosumer.address;
      return candidateLocation && normalizeLocation(candidateLocation) === normalizeLocation(location);
    });
    if (matches.length === 1 && !hasConflictingClientId) return { linked: matches[0], ambiguous: false };
    if (matches.length > 0) return { linked: null, ambiguous: true };
  }

  return { linked: null, ambiguous: candidates.length > 1 || hasConflictingClientId };
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
  const location = useLocation();
  const key = moduleKey || params.module;
  const cfg = MODULES[key];
  const startDocuments = key === "prosumator" && new URLSearchParams(location.search).get("start") === "documents";
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
  const [remoteSearchItems, setRemoteSearchItems] = useState(null);
  const [remoteSearchFailed, setRemoteSearchFailed] = useState(false);
  const [filterClient, setFilterClient] = useState("");
  const [filterOperator, setFilterOperator] = useState("");
  const [filterCounty, setFilterCounty] = useState("");
  const [filterLocality, setFilterLocality] = useState("");
  const [recordsView, setRecordsView] = useState("list");
  const [savedAt, setSavedAt] = useState(0);
  const [diuPre, setDiuPre] = useState(false);
  const [catalogImportsBusy, setCatalogImportsBusy] = useState(false);
  const [statusSavingId, setStatusSavingId] = useState("");

  const load = () => api.get(`/data/${key}`).then(async (r) => {
    const rows = Array.isArray(r.data) ? r.data : [];
    setItems(rows);
    const eid = new URLSearchParams(window.location.search).get("edit");
    if (!eid) return;
    let it = rows.find((x) => x.id === eid);
    if (!it) {
      try {
        const detail = await api.get(`/data/${key}/${encodeURIComponent(eid)}`);
        it = detail.data;
        if (it?.id) setItems((current) => current.some((x) => x.id === it.id) ? current : [it, ...current]);
      } catch (error) {
        const message = error?.response?.data?.detail || "Înregistrarea nu a putut fi încărcată. Verifică dacă ai acces la dosar.";
        toast.error(message);
        return;
      }
    }
    if (it?.id) {
      setForm({ ...it });
      setEditId(it.id);
      setChecks(it.checklist || {});
      const keepTestContext = new URLSearchParams(window.location.search).get("showTests") === "1";
      window.history.replaceState(null, "", keepTestContext ? `${window.location.pathname}?showTests=1` : window.location.pathname);
    } else {
      toast.error("Înregistrarea din link nu conține un identificator valid.");
    }
  }).catch((error) => {
    const message = error?.response?.data?.detail || "Nu s-au putut încărca înregistrările. Încearcă din nou.";
    toast.error(message);
  });

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setRemoteSearchItems(null);
      setRemoteSearchFailed(false);
      return undefined;
    }
    let active = true;
    setRemoteSearchItems(null);
    setRemoteSearchFailed(false);
    const timer = window.setTimeout(async () => {
      try {
        const { data } = await api.get(`/data/${key}`, { params: { q: term } });
        if (active) setRemoteSearchItems(Array.isArray(data) ? data : []);
      } catch {
        if (active) setRemoteSearchFailed(true);
      }
    }, 220);
    return () => { active = false; window.clearTimeout(timer); };
  }, [q, key]);

  useEffect(() => {
    setForm(null); setEditId(null); setChecks({}); setQ("");
    load();
    const refs = [...new Set((cfg.fields || []).filter((f) => f.type === "ref").map((f) => f.ref))];
    refs.forEach((ref) => {
      api.get(`/data/${ref}`).then((r) => {
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
          const site = clientSiteFor(client, pros?.pod);
          const kind = String(client.kind || "").toLowerCase();
          const caseName = params.get("case") || "";
          const requestType = caseName.toLocaleLowerCase("ro-RO").includes("spor") || caseName === "power-increase"
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
            client_site_id: site?.id || "",
            pod: site?.pod || client.pod || pros?.pod || "",
            operator: site?.operator || client.operator || pros?.operator || "",
            address: site?.address || client.address || pros?.address || "",
            cf_nr: site?.cf_nr || client.cf_nr || pros?.cf_nr || "",
            cadastral_nr: site?.cadastral_nr || client.cadastral_nr || pros?.cadastral_nr || "",
            locality: site?.locality || client.locality || "", county: site?.county || client.county || "",
            supplier: site?.supplier || client.supplier || "", nlc: site?.nlc || client.nlc || "",
            request_type: requestType,
            ...(/deer|distributie energie electrica romania/i.test(String(client.operator || pros?.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")) && (caseName.toLocaleLowerCase("ro-RO").includes("spor") || caseName === "power-increase") ? { deer_case: "Loc existent — spor de putere — Anexa 1" } : {}),
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
          const allPros = prosRes.data || [];
          const showTests = params.get("showTests") === "1";
          const linkedPros = allPros.filter((item) => item.client_id ? item.client_id === clientId : Boolean(client && normalizeClientName(item.client_name) === normalizeClientName(client.name)));
          const pros = prosId
            ? linkedPros.find((item) => item.id === prosId) || (showTests ? allPros.find((item) => item.id === prosId && (item.is_test || String(item.client_name || "").toUpperCase().includes("TEST"))) : null)
            : linkedPros.length === 1 ? linkedPros[0] : null;
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
          const site = clientSiteFor(client, pros?.pod);
          const grid = pros?.cef?.grid || {};
          const hasStorage = Boolean(pros && hasConfiguredStorage(pros));
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
            client_site_id: site?.id || "",
            address: pros?.address || site?.address || client.address || "",
            operator: pros?.operator || site?.operator || client.operator || "",
            pod: pros?.pod || site?.pod || client.pod || "",
            cf_nr: site?.cf_nr || client.cf_nr || "", cadastral_nr: site?.cadastral_nr || client.cadastral_nr || "",
            locality: site?.locality || client.locality || "", county: site?.county || client.county || "",
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
          window.history.replaceState(null, "", showTests ? `${window.location.pathname}?showTests=1` : window.location.pathname);
        }).catch(() => {});
      }
    }
    // eslint-disable-next-line
  }, [key, location.search]);

  const openNew = () => { setForm(key === "atr" ? { date: new Date().toISOString().slice(0, 10), submission_mode: "Solicitantul depune direct" } : {}); setEditId(null); setChecks({}); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); };
  const updateQuickStatus = async (item, status) => {
    if (!status || status === (item.workflow_status || item.status)) return;
    setStatusSavingId(item.id);
    try {
      const { data } = await api.patch("/data/" + encodeURIComponent(key) + "/" + encodeURIComponent(item.id) + "/status", { status });
      setItems((current) => current.map((row) => row.id === item.id ? { ...row, workflow_status: data.status, updated_at: data.updated_at } : row));
      toast.success("Stadiul dosarului a fost actualizat.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Stadiul nu a putut fi actualizat.");
    } finally {
      setStatusSavingId("");
    }
  };
  const setVal = (name, value) => {
    if (key === "atr" && name === "client_name") {
      const client = (refOptions.clients || []).find((c) => c.label === value);
      if (!client) {
        setForm((p) => ({ ...p, client_name: value, client_id: "", client_site_id: "", pros_id: "", pod: "", operator: "", address: "",
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
      const site = clientSiteFor(client, linked?.pod);
      const clientKind = String(client.kind || "").toLowerCase();
      const applicantType = /jurid/.test(clientKind) ? "Persoană juridică" : /fiz|persoan/.test(clientKind) ? "Persoană fizică" : "";
      const next = {
        client_name: value, client_id: client.id, client_site_id: site?.id || "",
        pod: site?.pod || client.pod || linked?.pod || "",
        operator: site?.operator || client.operator || linked?.operator || "",
        address: site?.address || client.address || linked?.address || "",
        cf_nr: site?.cf_nr || client.cf_nr || linked?.cf_nr || "",
        cadastral_nr: site?.cadastral_nr || client.cadastral_nr || linked?.cadastral_nr || "",
        locality: site?.locality || client.locality || "", county: site?.county || client.county || "",
        supplier: site?.supplier || client.supplier || "", nlc: site?.nlc || client.nlc || "",
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
          if (/deer|distributie energie electrica romania/i.test(String(next.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""))) next.deer_case = "Loc existent — spor de putere — Anexa 1";
        }
      }
      setForm((p) => ({ ...p, ...next }));
      return;
    }
    if (key === "power" && name === "client_name") {
      const client = (refOptions.clients || []).find((item) => item.label === value);
      if (!client) {
        setForm((prev) => ({ ...prev, client_name: value, client_id: "", client_site_id: "", address: "", operator: "", pod: "" }));
        return;
      }
      const site = clientSiteFor(client);
      setForm((prev) => ({ ...prev, client_name: value, client_id: client.id, client_site_id: site?.id || "",
        ...Object.fromEntries(CLIENT_SITE_FIELDS.map((field) => [field, site?.[field] || client[field] || ""])) }));
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
      const linkedPros = (refOptions.prosumator || []).find((item) => item.id === form.pros_id);
      const clearMismatch = Boolean(linkedPros?.pod && pod && String(linkedPros.pod).replace(/\\s+/g, "").toUpperCase() !== pod);
      setForm((p) => ({ ...p, ...(clearMismatch ? { pros_id: "", current_supply_desc: "" } : {}),
        pod, ...(detected ? { operator: detected } : {}), pod_check_note: note }));
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
  const prosumerFilterRows = useMemo(() => {
    const clients = refOptions.clients || [];
    return visibleItems.map((item) => {
      const client = clients.find((candidate) => (item.client_id && candidate.id === item.client_id)
        || (item.client_name && normalizeClientName(candidate.name) === normalizeClientName(item.client_name)));
      return {
        item,
        client,
        clientName: item.client_name || client?.name || "",
        operator: item.operator || client?.operator || "",
        county: item.county || client?.county || "",
        locality: item.locality || item.city || item.town || item.commune || item.village
          || client?.locality || client?.city || client?.town || client?.commune || client?.village || "",
        searchable: JSON.stringify({ ...item, client: client || {} }).toLocaleLowerCase("ro-RO"),
      };
    });
  }, [visibleItems, refOptions.clients]);
  const filterValues = useMemo(() => {
    const unique = (key) => [...new Set(prosumerFilterRows.map((row) => String(row[key] || "").trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "ro"));
    return { clients: unique("clientName"), operators: unique("operator"), counties: unique("county"), localities: unique("locality") };
  }, [prosumerFilterRows]);
  const filtered = useMemo(() => {
    const ql = q.trim().toLocaleLowerCase("ro-RO");
    const isProsumator = key === "prosumator";
    const prosumerById = new Map(prosumerFilterRows.map((row) => [row.item.id, row]));
    const source = remoteSearchItems === null
      ? visibleItems
      : (showTestRecords ? remoteSearchItems : remoteSearchItems.filter((item) => !["clients", "prosumator", "diu"].includes(key) || !isTestRecord(item)));
    return source.map((entry) => {
      if (!isProsumator) return { item: entry, searchable: JSON.stringify(entry).toLocaleLowerCase("ro-RO") };
      return prosumerById.get(entry.id) || {
        item: entry,
        clientName: entry.client_name || "",
        operator: entry.operator || "",
        county: entry.county || "",
        locality: entry.locality || entry.city || entry.town || entry.commune || entry.village || "",
        searchable: JSON.stringify(entry).toLocaleLowerCase("ro-RO"),
      };
    }).filter((row) => {
      if (ql && remoteSearchItems === null && !row.searchable.includes(ql)) return false;
      if (isProsumator && filterClient && normalizeClientName(row.clientName) !== normalizeClientName(filterClient)) return false;
      if (isProsumator && filterOperator && normalizeClientName(row.operator) !== normalizeClientName(filterOperator)) return false;
      if (isProsumator && filterCounty && normalizeClientName(row.county) !== normalizeClientName(filterCounty)) return false;
      if (isProsumator && filterLocality && normalizeClientName(row.locality) !== normalizeClientName(filterLocality)) return false;
      return true;
    }).map((row) => row.item);
  }, [key, visibleItems, prosumerFilterRows, q, remoteSearchItems, showTestRecords, filterClient, filterOperator, filterCounty, filterLocality]);

  const inboxItems = useMemo(() => {
    if (key !== "prosumator") return [];
    return visibleItems
      .filter((item) => String(item.next_action || "").trim())
      .sort((a, b) => String(a.next_action_due || "9999-12-31").localeCompare(String(b.next_action_due || "9999-12-31")));
  }, [key, visibleItems]);

  const checkedCount = cfg.checklist ? cfg.checklist.filter((c) => checks[c]).length : 0;
  const currentOdStage = Math.max(0, PROSUMER_OD_STAGES.indexOf(form?.operator_stage));
  const operatorStageDocuments = form?.operator_stage_documents || {};
  const currentOperatorStageDocuments = operatorStageDocuments[String(currentOdStage)] || {};
  const currentOdGuidance = PROSUMER_OD_STAGE_GUIDANCE[currentOdStage] || [];
  const checkedOdGuidance = currentOdGuidance.filter((item) => currentOperatorStageDocuments[item]).length;
  const formClient = form?.client_id ? (refOptions.clients || []).find((client) => client.id === form.client_id) : null;
  const formClientSites = clientConsumptionSites(formClient);
  const formClientSite = formClientSites.find((site) => String(site.id) === String(form?.client_site_id || ""))
    || clientSiteFor(formClient, form?.pod);

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
              <DossierDocumentStart autoOpen={startDocuments} onCreated={(data) => { setForm({ ...data }); setEditId(data.id); setChecks(data.checklist || {}); load(); }} />
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
          {key === "prosumator" && editId && <section className="mb-5 rounded-xl border p-3 sm:p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="prosumer-quick-actions">
          {key === "prosumator" && editId && <section className="mb-5 rounded-xl border p-3 sm:p-4" style={{ borderColor: "var(--line)", background: "#fff" }} data-testid="prosumer-operator-progress">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div><h3 className="text-sm font-bold">Urmărirea dosarului la operator</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Selectează etapa curentă pentru a vedea progresul până la punerea sub tensiune.</p></div>
              <span className="rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: form.operator_stage ? "#eaf1ff" : "#f1f5f9", color: form.operator_stage ? "var(--blue)" : "var(--muted)" }} data-testid="prosumer-stage-count">{form.operator_stage ? `Etapa ${currentOdStage + 1} din ${PROSUMER_OD_STAGES.length}` : "Etapă nealeasă"}</span>
            </div>
            <div className="grid grid-cols-9 gap-1.5" role="group" aria-label="Etapele dosarului la operator">
              {PROSUMER_OD_STAGES.map((stage, index) => <button key={stage} type="button" title={stage} aria-label={`Etapa ${index + 1}: ${stage}`} aria-pressed={form.operator_stage === stage} onClick={() => setVal("operator_stage", stage)} className="min-h-9 rounded-lg border text-xs font-bold transition" style={{ borderColor: form.operator_stage === stage ? "var(--blue)" : "var(--line)", background: form.operator_stage === stage ? "var(--blue)" : (form.operator_stage && index < currentOdStage ? "#eaf1ff" : "#fff"), color: form.operator_stage === stage ? "#fff" : (form.operator_stage && index < currentOdStage ? "var(--blue)" : "var(--muted)") }} data-testid={`prosumer-stage-${index + 1}`}>{index + 1}</button>)}
            </div>
            <label className="den-field mt-3 block"><span className="text-xs font-semibold">Etapa curentă</span>
              <select className="den-input mt-1" value={form.operator_stage || ""} onChange={(event) => setVal("operator_stage", event.target.value)} data-testid="prosumer-stage-select">
                <option value="">Alege etapa curentă…</option>{PROSUMER_OD_STAGES.map((stage, index) => <option key={stage} value={stage}>{index + 1}. {stage}</option>)}
              </select>
            </label>
            {form.operator_stage && <p className="mt-2 text-xs font-medium" style={{ color: "var(--blue)" }}>{form.operator_stage}</p>}
            {form.operator_stage && <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "#fbfcfe" }} data-testid="prosumer-stage-guidance">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><div className="text-xs font-bold">Checklist pentru etapa aceasta</div><span className="text-[11px] font-semibold" style={{ color: "var(--muted)" }} data-testid="prosumer-stage-checklist-progress">{checkedOdGuidance} / {currentOdGuidance.length} verificate</span></div>
              <ul className="grid gap-1.5 text-xs leading-5 sm:grid-cols-2" style={{ color: "var(--muted)" }}>
                {currentOdGuidance.map((item) => <li key={item}><label className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-white"><input className="mt-1 shrink-0" type="checkbox" checked={Boolean(currentOperatorStageDocuments[item])} onChange={(event) => setVal("operator_stage_documents", { ...operatorStageDocuments, [String(currentOdStage)]: { ...currentOperatorStageDocuments, [item]: event.target.checked } })} data-testid={`prosumer-stage-check-${currentOdStage + 1}`} /><span>{item}</span></label></li>)}
              </ul>
              <p className="mt-2 text-[11px] leading-4" style={{ color: "var(--muted)" }}>Bifele se salvează împreună cu dosarul și arată ce ai verificat sau pregătit. Nu marchează documente ca depuse și nu transmit date operatorului. Formularul exact depinde de operator, tipul cererii și ATR.</p>
            </div>}
            <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>Stadiul se păstrează împreună cu dosarul când apeși „Salvează”. Actualizarea stadiului nu depune cereri în portalul operatorului.</p>
          </section>}
          
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div><div className="text-sm font-bold">{form.client_name || "Dosar prosumator"}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{[form.operator, form.pod && `POD ${form.pod}`, form.status].filter(Boolean).join(" · ")}</div></div>
              <span className="text-xs font-semibold" style={{ color: "var(--blue)" }}>Acțiuni rapide dosar</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="inline-flex min-h-10 items-center rounded-lg px-3 py-2 text-xs font-bold text-white" style={{ background: "var(--blue)" }} onClick={() => openAuthenticatedFile(`/dossier/${encodeURIComponent(editId)}/export`)} data-testid="quick-prosumer-pdf">Dosar complet PDF</button>
              <button type="button" className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/sld/${encodeURIComponent(editId)}/pdf?download=1`, `schema_monofilara_${String(editId).slice(0, 8)}.pdf`)} data-testid="quick-prosumer-schema">Schema monofilară</button>
              <button type="button" className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/docs/buletin_priza/${encodeURIComponent(editId)}`, `buletin_pram_${String(editId).slice(0, 8)}.pdf`)} data-testid="quick-prosumer-pram">Buletin PRAM</button>
              <button type="button" className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile(`/docs/pv_pif/${encodeURIComponent(editId)}`)} data-testid="quick-prosumer-pif">Proces-verbal PIF</button>
              {form.client_id && <a className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(form.client_id)}&prosId=${encodeURIComponent(editId)}`} data-testid="quick-prosumer-atr">Cerere ATR</a>}
              {form.client_id && <a className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(form.client_id)}&prosId=${encodeURIComponent(editId)}&case=power-increase`} data-testid="quick-prosumer-power">Spor de putere</a>}
              {form.client_id && <a className="inline-flex min-h-10 items-center rounded-lg border bg-white px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/diu?new=diu&clientId=${encodeURIComponent(form.client_id)}&prosId=${encodeURIComponent(editId)}`} data-testid="quick-prosumer-diu">Creează DI-U</a>}
            </div>
          </section>}
          {key === "prosumator" ? <ProsumatorQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} onImportsBusyChange={setCatalogImportsBusy} /> : key === "atr" ? <AtrQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : key === "diu" ? <DiuQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : (
            <div className="grid sm:grid-cols-2 gap-4">
              {cfg.fields.map((f, i) => <Field key={f.name || `s${i}`} f={f} value={form[f.name]} onChange={(name, value) => setVal(name, value)} refOptions={refOptions} ai={can(user, "ai_gpt") ? { module: key, form } : null} />)}
            </div>
          )}
          {["atr", "power"].includes(key) && formClient && formClientSites.length > 0 && <section className="mt-4 rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="client-consumption-site-selector">
            <label className="den-field"><span>Loc de consum al clientului</span>
              <select className="den-input" value={form.client_site_id || formClientSite?.id || ""} onChange={(event) => {
                const site = formClientSites.find((item) => String(item.id) === String(event.target.value));
                if (!site) return;
                setForm((prev) => {
                  const linkedPros = (refOptions.prosumator || []).find((item) => item.id === prev.pros_id);
                  const clearMismatch = linkedPros && !clientSiteMatchesPros(site, linkedPros);
                  return { ...prev, ...(clearMismatch ? { pros_id: "", current_supply_desc: "" } : {}),
                    client_site_id: site.id, ...Object.fromEntries(CLIENT_SITE_FIELDS.map((field) => [field, site[field] || ""])) };
                });
              }} data-testid="client-consumption-site-select">
                {formClientSites.map((site, index) => <option key={site.id} value={site.id}>{clientSiteLabel(site, index)}</option>)}
              </select>
            </label>
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>POD-ul și adresa selectate se completează în cerere. Verifică valorile față de factura locului de consum.</p>
          </section>}
          {key === "atr" && form.pod_check_note && <div className="mt-3 rounded-lg border px-3 py-2 text-sm" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>{form.pod_check_note}</div>}

          {cfg.checklist && key !== "prosumator" && key !== "diu" && (
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
          {key === "clients" && <ClientDocs client={form} onChange={(docs, fields = {}) => { setVal("docs", docs); if (Object.keys(fields).length) setForm((current) => ({ ...current, ...fields, docs })); }} />}
          {key === "clients" && editId && <SignRequests clientName={form.name} />}

          <div className="flex gap-2 mt-6 den-noprint">
            <Btn onClick={save} disabled={key === "prosumator" && catalogImportsBusy} data-testid="save-btn">{catalogImportsBusy ? "Se preiau documentele…" : "Salvează"}</Btn>
            <Btn variant="secondary" onClick={() => window.print()} data-testid="pdf-btn">Tipărește / PDF</Btn>
            <Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>
          </div>
        </div>
      )}

      <div className="den-panel" data-testid="saved-records">
        {key === "prosumator" && <section className="mb-5 rounded-xl border bg-white p-4 shadow-sm" style={{ borderColor: "var(--line)" }} aria-label="Inbox de azi" data-testid="prosumer-action-inbox">
          <div className="flex items-center justify-between gap-2">
            <div><h2 className="text-sm font-bold">Inbox de azi</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Acțiunile și termenele introduse în fiecare dosar apar aici.</p></div>
            <span className="rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: "#eaf1ff", color: "var(--blue)" }} data-testid="prosumer-action-count">{inboxItems.length}</span>
          </div>
          {inboxItems.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {inboxItems.map((item) => {
              const dueDate = item.next_action_due ? new Date(`${item.next_action_due}T00:00:00`) : null;
              const today = new Date(); today.setHours(0, 0, 0, 0);
              const dueLabel = !dueDate || Number.isNaN(dueDate.getTime()) ? "Fără termen"
                : dueDate < today ? "Întârziată"
                  : dueDate.getTime() === today.getTime() ? "Astăzi"
                    : new Intl.DateTimeFormat("ro-RO", { day: "2-digit", month: "short" }).format(dueDate);
              const overdue = dueLabel === "Întârziată";
              return <article key={item.id} className="flex items-start justify-between gap-3 rounded-lg border px-3 py-2.5" style={{ borderColor: "var(--line)", background: "#fbfcfe" }}>
                <div className="min-w-0"><div className="truncate text-xs font-bold">{item.client_name || item.number || "Dosar prosumator"}</div><div className="mt-1 text-xs">{item.next_action}</div></div>
                <button type="button" className="shrink-0 rounded-full px-2 py-1 text-[10px] font-bold" style={{ background: overdue ? "#fff0ed" : "#eaf1ff", color: overdue ? "#b43b2f" : "var(--blue)" }} onClick={() => openEdit(item)} aria-label={`Deschide acțiunea ${item.next_action} pentru ${item.client_name || item.number || "dosar"}`}>{dueLabel}</button>
              </article>;
            })}
          </div> : <p className="mt-3 rounded-lg px-3 py-3 text-xs" style={{ color: "var(--muted)", background: "#f8fafd" }}>Nu ai acțiuni planificate. Deschide un dosar și completează „Următoarea acțiune” și, opțional, termenul.</p>}
        </section>}

        {onlyTestRecords && showTestRecords === true && <div className="mb-4 rounded-lg border px-3 py-2 text-xs font-medium" style={{ borderColor: "#f2d28c", background: "#fff9e9", color: "#73520b" }} role="status">Sunt afișate dosare demonstrative marcate TEST. Folosește-le numai pentru verificarea fluxului; nu conțin date reale și nu se depun.</div>}
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <h2 className="text-lg font-bold">Înregistrări salvate <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({filtered.length})</span></h2>
          {hiddenTestCount > 0 && <button type="button" className="text-xs underline" onClick={() => setShowTestRecords((value) => !value)}>{showTestRecords === true ? "Ascunde" : "Arată"} înregistrările TEST ({hiddenTestCount})</button>}
          {key === "prosumator" && <div className="inline-flex rounded-lg border p-1" style={{ borderColor: "var(--line)" }} role="group" aria-label="Mod vizualizare dosare">
            <button type="button" onClick={() => setRecordsView("board")} aria-pressed={recordsView === "board"} className="rounded-md px-3 py-1.5 text-xs font-semibold" style={{ background: recordsView === "board" ? "#eaf1ff" : "transparent", color: recordsView === "board" ? "var(--blue)" : "var(--muted)" }}>Kanban</button>
            <button type="button" onClick={() => setRecordsView("list")} aria-pressed={recordsView === "list"} className="rounded-md px-3 py-1.5 text-xs font-semibold" style={{ background: recordsView === "list" ? "#eaf1ff" : "transparent", color: recordsView === "list" ? "var(--blue)" : "var(--muted)" }}>Listă</button>
          </div>}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input data-testid="search-input" className="den-input w-[240px]" style={{ paddingLeft: 34 }} placeholder="Caută..." value={q} onChange={(e) => setQ(e.target.value)} />
            {remoteSearchFailed && <span className="mt-1 block text-[11px] text-amber-700" role="status">Căutarea online nu răspunde; folosesc înregistrările deja încărcate.</span>}
          </div>
        </div>

        {key === "prosumator" && <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4" data-testid="prosumator-filters" aria-label="Filtrează dosarele">
          <select className="den-input min-w-0" value={filterClient} onChange={(e) => setFilterClient(e.target.value)} aria-label="Filtrează după client" data-testid="filter-client">
            <option value="">Toți clienții</option>{filterValues.clients.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select className="den-input min-w-0" value={filterOperator} onChange={(e) => setFilterOperator(e.target.value)} aria-label="Filtrează după operator" data-testid="filter-operator">
            <option value="">Toți operatorii</option>{filterValues.operators.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select className="den-input min-w-0" value={filterCounty} onChange={(e) => setFilterCounty(e.target.value)} aria-label="Filtrează după județ" data-testid="filter-county">
            <option value="">Toate județele</option>{filterValues.counties.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select className="den-input min-w-0" value={filterLocality} onChange={(e) => setFilterLocality(e.target.value)} aria-label="Filtrează după localitate" data-testid="filter-locality">
            <option value="">Toate localitățile</option>{filterValues.localities.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          {(filterClient || filterOperator || filterCounty || filterLocality) && <button type="button" className="text-xs font-semibold underline justify-self-start sm:col-span-2 xl:col-span-4" onClick={() => { setFilterClient(""); setFilterOperator(""); setFilterCounty(""); setFilterLocality(""); }} data-testid="filter-clear">Șterge filtrele</button>}
        </div>}

        {filtered.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu există înregistrări încă.</div>
        ) : (
          <>
          {key === "prosumator" && recordsView === "board" && <div className="mb-4 overflow-x-auto" data-testid="prosumator-kanban">
            <div className="grid min-w-[280px] gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[...new Set(filtered.map((item) => String(item.workflow_status || item.status || item.operator_stage || "Dosar în pregătire").trim()))].map((status) => {
                const group = filtered.filter((item) => String(item.workflow_status || item.status || item.operator_stage || "Dosar în pregătire").trim() === status);
                return <section key={status} className="rounded-xl border p-3" style={{ borderColor: "var(--line)", background: "var(--bg)" }} aria-label={`Stadiu ${status}`}>
                  <div className="mb-3 flex items-center justify-between gap-2 text-sm font-bold"><span>{status}</span><span className="rounded-full px-2 py-0.5 text-xs" style={{ background: "#eaf1ff", color: "var(--blue)" }}>{group.length}</span></div>
                  <div className="grid gap-2">{group.map((item) => {
                    const client = prosumerFilterRows.find((row) => row.item.id === item.id)?.client;
                    const inverters = item.cef?.inverters || [];
                    const parsePower = (value) => {
                      const parsed = Number(String(value ?? "").replace(",", "."));
                      return Number.isFinite(parsed) ? parsed : 0;
                    };
                    const inverterKw = inverters.reduce((total, inverter) => {
                      const power = parsePower(inverter.p_nom_kw || inverter.p_max_kw);
                      const count = Math.max(1, parsePower(inverter.count || inverter.quantity) || 1);
                      return total + power * count;
                    }, 0) || parsePower(item.inverter_kw);
                    const inverterModels = [...new Set(inverters.map((inverter) => inverter.brand_model || inverter.model).filter(Boolean))];
                    const panelModels = [...new Set(inverters.map((inverter) => inverter.panel_model).filter(Boolean))];
                    const batteryModels = [...new Set([
                      ...inverters.filter((inverter) => inverter.battery_mode === "own").map((inverter) => inverter.battery?.model),
                      ...(item.cef?.shared_batteries || []).map((battery) => battery.model),
                    ].filter(Boolean))];
                    const pod = item.pod || client?.pod || "";
                    const pvKwp = installedPanelKwp(item);
                    return <article key={item.id} className="rounded-lg border bg-white p-3 shadow-sm" style={{ borderColor: "var(--line)" }}>
                      <div className="font-semibold leading-5">{item.client_name || item.number || "Dosar prosumator"}</div>
                      <div className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>{item.number || "Fără număr"} · {item.request_type || "Tip cerere neales"}</div>
                      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] leading-4">
                        <div><span style={{ color: "var(--muted)" }}>POD </span>{pod || "necompletat"}</div>
                        <div><span style={{ color: "var(--muted)" }}>Distribuitor </span>{item.operator || client?.operator || "neales"}</div>
                        <div><span style={{ color: "var(--muted)" }}>Evacuare </span>{item.power ? String(item.power) + " kW" : "necompletată"}</div>
                        <div><span style={{ color: "var(--muted)" }}>Invertor </span>{inverterKw ? Number(inverterKw.toFixed(2)) + " kW" : "neales"}</div>
                        <div><span style={{ color: "var(--muted)" }}>Panouri </span>{pvKwp ? String(pvKwp) + " kWp" : (panelModels.length ? panelModels.join(", ") : "neprecizate")}</div>
                        <div><span style={{ color: "var(--muted)" }}>Baterie </span>{batteryModels.length ? batteryModels.join(", ") : "fără date"}</div>
                      </div>
                      {(inverterModels.length > 0 || panelModels.length > 0) && <div className="mt-2 border-t pt-2 text-[11px] leading-4" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>
                        {[inverterModels.length > 0 ? "Invertor: " + inverterModels.join(", ") : "", panelModels.length > 0 ? "Panouri: " + panelModels.join(", ") : ""].filter(Boolean).join(" · ")}
                      </div>}
                      <button type="button" className="mt-2 rounded-md border px-2.5 py-1.5 text-xs font-semibold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} onClick={() => openEdit(item)}>Deschide</button>
                    </article>;
                  })}</div>
                </section>;
              })}
            </div>
          </div>}
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
                  <a className={actionClass} style={{ color: "var(--blue)", borderColor: "var(--line)" }} href={base + "&case=" + encodeURIComponent("power-increase")}>Spor de putere</a>
                  <a className={actionClass} style={{ color: "var(--blue)", borderColor: "var(--line)" }} href={"/diu?new=diu&clientId=" + encodeURIComponent(it.id) + (pros ? "&prosId=" + encodeURIComponent(pros.id) : "") + ((showTestRecords || isTestRecord(it) || (pros && isTestRecord(pros))) ? "&showTests=1" : "")}>Creează DI-U</a>
                </div>
                {(pros || diu) && <details className="mt-3 border-t pt-3" style={{ borderColor: "var(--line)" }}>
                  <summary className="cursor-pointer text-xs font-semibold" style={{ color: "var(--blue)" }}>Descarcă documentele disponibile</summary>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {pros && <>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile("/dossier/" + pros.id + "/export")}>Dosar prosumator</button>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/sld/" + pros.id + "/pdf?download=1", "schema_monofilara_" + pros.id.slice(0, 8) + ".pdf")}>Schema monofilara</button>
                      <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/docs/buletin_priza/" + pros.id, "pram_priza_" + pros.id.slice(0, 8) + ".pdf")}>Buletin PRAM</button>
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
          {key === "prosumator" && recordsView === "list" && <div className="grid gap-3 sm:hidden" data-testid="mobile-prosumer-actions">
            {filtered.map((it) => {
              const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
              const diu = linkedDiu.find((d) => d.pros_id === it.id || (d.client_id ? d.client_id === it.client_id : normalize(d.client_name) === normalize(it.client_name)));
              const actionClass = "inline-flex min-h-9 items-center justify-center rounded-lg border px-3 py-2 text-xs font-semibold";
              return <article key={it.id} className="rounded-xl border p-4 shadow-sm" style={{ borderColor: "var(--line)", background: "#fff" }} data-testid={`prosumer-card-${it.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-bold">{it.client_name || it.number || "Dosar prosumator"}</h3>
                    <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>{it.number || "Fără număr"} · {it.power || it._kwp || "Putere necompletată"} kW</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{it.operator || "Operator neales"}</p>
                    <label className="mt-2 flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      Stadiu
                      <select className="den-input min-h-9 min-w-0 py-1 text-xs" value={it.workflow_status || it.status || "În lucru"} disabled={Boolean(statusSavingId)} onChange={(event) => updateQuickStatus(it, event.target.value)} aria-label={"Stadiu dosar " + (it.number || it.id)} data-testid={"quick-status-mobile-" + it.id}>
                        {[...new Set([it.workflow_status, it.status, ...PROSUMER_QUICK_STATUSES].filter(Boolean))].map((status) => <option key={status} value={status}>{status}</option>)}
                      </select>
                    </label>
                  </div>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => openEdit(it)}>Deschide</button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/export`)}>Dosar PDF</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/sld/${it.id}/pdf?download=1`, `schema_monofilara_${it.id.slice(0, 8)}.pdf`)}>Schema</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/docs/buletin_priza/${it.id}`, `pram_priza_${it.id.slice(0, 8)}.pdf`)}>PRAM priză</button>
                  <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/docs/pv_pif/${it.id}`, `pif_${it.id.slice(0, 8)}.pdf`)}>Proces verbal PIF</button>
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}`}>Cerere ATR</a>}
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/cerere-atr?new=atr&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}&case=${encodeURIComponent("power-increase")}`}>Spor de putere</a>}
                  {it.client_id && <a className={actionClass} style={{ borderColor: "var(--line)", color: "var(--blue)" }} href={`/diu?new=diu&clientId=${encodeURIComponent(it.client_id)}&prosId=${encodeURIComponent(it.id)}${(showTestRecords || isTestRecord(it)) ? "&showTests=1" : ""}`}>Creează DI-U</a>}
                  {diu && <button type="button" className={actionClass} style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`, `pram_priza_diu_${diu.id.slice(0, 8)}.pdf`)}>PRAM DI-U</button>}
                </div>
              </article>;
            })}
          </div>}
          {key === "atr" && <div className="grid gap-3 sm:hidden" data-testid="atr-mobile-cards">
            {filtered.map((it) => {
              const { linked, ambiguous } = resolveLinkedProsumer(it, linkedProsumer);
              const equipmentLabel = linked ? (() => {
                const inverters = linked.cef?.inverters || [];
                const inverterNames = [...new Set(inverters.map((item) => item.brand_model).filter(Boolean))].map((name) => `Invertor: ${name}`);
                const panelCounts = new Map();
                for (const inverter of inverters) {
                  const model = String(inverter.panel_model || "").trim();
                  if (!model) continue;
                  const count = (inverter.strings || []).reduce((sum, item) => sum + (Number(item.panels) || 0), 0) * Math.max(1, Number(inverter.count) || 1);
                  panelCounts.set(model, (panelCounts.get(model) || 0) + count);
                }
                const panelNames = [...panelCounts].map(([model, count]) => `Panouri: ${model}${count ? ` (${count} buc.)` : ""}`);
                const batteries = [
                  ...inverters.filter((item) => item.battery_mode === "own" && item.battery?.model)
                    .map((item) => ({ ...item.battery, modules: (Number(item.battery.modules) || 1) * Math.max(1, Number(item.count) || 1) })),
                  ...(linked.cef?.shared_batteries || []),
                ];
                if (!batteries.length && (linked.battery || linked.storage)) {
                  const legacy = linked.battery || linked.storage;
                  batteries.push(typeof legacy === "string" ? { model: legacy } : legacy);
                }
                const batteryNames = [...new Set(batteries.map((battery) => [
                  battery.model || "Baterie",
                  battery.modules > 1 ? `× ${battery.modules}` : "",
                  battery.voltage ? `${battery.voltage} V` : "",
                  battery.ah ? `${battery.ah} Ah` : "",
                  battery.i_max ? `I max ${battery.i_max} A` : "",
                  battery.kwh ? `${battery.kwh} kWh` : "",
                  battery.coupling ? `cuplare ${battery.coupling}` : "",
                ].filter(Boolean).join(" · ")))].map((name) => `Baterie: ${name}`);
                return [...inverterNames, ...panelNames, ...batteryNames].join(" · ") || "În dosar";
              })() : ambiguous ? "Selectează dosarul prosumator în cerere" : "Nu este asociat un dosar prosumator";
              const isDeer = /deer|distributie energie electrica romania/i.test(String(it.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""));
              return <article key={it.id} className="rounded-xl border bg-white p-4 shadow-sm" style={{ borderColor: "var(--line)" }} data-testid={`atr-mobile-card-${it.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-bold">{it.client_name || "Solicitant necompletat"}</h3>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{it.operator || "Operator necompletat"}</p>
                  </div>
                  <span className="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold" style={{ background: linked ? "#dcfce7" : "#fff7ed", color: linked ? "#166534" : "#9a6700" }}>{linked ? "Echipamente legate" : ambiguous ? "Alege dosarul PV" : "Lipsește dosar PV"}</span>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div><dt style={{ color: "var(--muted)" }}>Procedură</dt><dd className="mt-0.5 font-semibold">{it.deer_case || it.request_type || "De selectat"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>POD</dt><dd className="mt-0.5 font-semibold">{it.pod || "De completat"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>Putere absorbită</dt><dd className="mt-0.5 font-semibold">{it.p_abs_kw ? `${it.p_abs_kw} kW` : "—"}</dd></div>
                  <div><dt style={{ color: "var(--muted)" }}>Echipamente</dt><dd className="mt-0.5 font-semibold">{equipmentLabel}</dd></div>
                </dl>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button type="button" className="min-h-10 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openEdit(it)} data-testid={`edit-mobile-${it.id}`}>Editează cererea</button>
                  <button type="button" className="min-h-10 rounded-lg px-3 text-xs font-semibold text-white" style={{ background: "var(--blue)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/package.zip", "Pachet_ATR.zip")} data-testid={`atr-package-mobile-${it.id}`}>Descarcă dosarul ZIP</button>
                  {isDeer && <button type="button" className="col-span-2 min-h-10 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/official-docx", "Anexa_DEER_completata_" + it.id.slice(0, 8) + ".docx")}>Descarcă Anexa DEER completată</button>}
                </div>
              </article>;
            })}
          </div>}
          <div className={key === "prosumator" && recordsView === "board" ? "hidden" : (["clients", "prosumator", "atr"].includes(key) ? "hidden overflow-x-auto sm:block" : "overflow-x-auto")}>
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
                    {cfg.columns.map((c) => <td key={c.key} className="px-3 py-3 whitespace-nowrap">
                      {key === "prosumator" && c.key === "status" ? (
                        <select className="den-input min-h-9 min-w-[150px] py-1 text-xs" value={it.workflow_status || it.status || "În lucru"} disabled={Boolean(statusSavingId)} onChange={(event) => updateQuickStatus(it, event.target.value)} aria-label={"Stadiu dosar " + (it.number || it.id)} data-testid={"quick-status-" + it.id}>
                          {[...new Set([it.workflow_status, it.status, ...PROSUMER_QUICK_STATUSES].filter(Boolean))].map((status) => <option key={status} value={status}>{status}</option>)}
                        </select>
                      ) : (it[c.key] || "—")}
                    </td>)}
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
                        const diuUrl = "/diu?new=diu&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "") + ((showTestRecords || isTestRecord(it) || (dossier && isTestRecord(dossier))) ? "&showTests=1" : "");
                        return <span className="inline-flex max-w-[204px] items-center flex-wrap gap-1">
                          <button type="button" className={linkClass} onClick={() => { window.location.href = diuUrl; }}>Creează DI-U</button>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "")}>Cerere ATR</a>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "") + "&case=" + encodeURIComponent("power-increase")}>Spor de putere</a>
                          {clientProsumerDossiers.length > 1 && <span className="basis-full text-[10px] text-amber-800">Mai multe dosare PV: selectează-l pe cel corect în ATR / DI-U.</span>}
                          {clientDiuDossiers.length > 1 && <span className="basis-full text-[10px] text-amber-800">Mai multe dosare DI-U: deschide dosarul dorit pentru documente și PRAM.</span>}
                          {dossier && <>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${dossier.id}/export`)}>Dosar PDF</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/sld/${dossier.id}/pdf?download=1`, `schema_monofilara_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă schemă</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/docs/pv_pif/${dossier.id}`, `pif_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă PIF</button>
                            <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/docs/buletin_priza/${dossier.id}`, `pram_priza_${dossier.id.slice(0, 8)}.pdf`)}>Descarcă PRAM</button>
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
                        const diuUrl = it.client_id ? "/diu?new=diu&clientId=" + encodeURIComponent(it.client_id) + "&prosId=" + encodeURIComponent(it.id) + ((showTestRecords || isTestRecord(it)) ? "&showTests=1" : "") : "";
                        return <span className="inline-flex items-center flex-wrap gap-y-1">
                          {diuUrl && <a className={linkClass} href={diuUrl}>Creează DI-U</a>}
                          {it.client_id && <a className={linkClass} href={atrUrl}>Cerere ATR</a>}
                          {it.client_id && <a className={linkClass} href={atrUrl + "&case=" + encodeURIComponent("power-increase")}>Spor de putere</a>}
                          <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/export`)}>Dosar PDF</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/sld/${it.id}/pdf?download=1`, `schema_monofilara_${it.id.slice(0, 8)}.pdf`)}>Descarcă schemă</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/docs/pv_pif/${it.id}`, `pif_${it.id.slice(0, 8)}.pdf`)}>Descarcă PIF</button>
                          <button type="button" className={linkClass} onClick={() => downloadAuthenticatedFile(`/docs/buletin_priza/${it.id}`, `pram_priza_${it.id.slice(0, 8)}.pdf`)}>Descarcă PRAM</button>
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

