Warning: truncated output (original token count: 34501)
Total output lines: 1596

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api, API, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";
import { hasConfiguredStorage } from "@/lib/cefStorage";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X } from "lucide-react";
import { toast } from "sonner";
import { GeneratedDocs } from "@/components/ProsumatorTools";
import { DossierDocumentStart } from "@/components/dossier/DossierDocumentStart";
import { ClientConversation } from "@/components/dossier/ClientConversation";
import { DossierActivity } from "@/components/dossier/DossierActivity";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs } from "@/components/dossier/ClientDocs";
import { SignRequests } from "@/components/sign/SignRequests";
import { SldPanel } from "@/components/sld/SldPanel";
import { DossierSigners } from "@/components/dossier/DossierSigners";

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
import { installationIsConfigured } from "@/lib/prosumerWorkflow.mjs";

function installedPanelKwp(pros) {
  if (!pros) return "";
  const number = (value) => {
    const parsed = Number(String(value ?? "").replace(",", "."));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const inverters = pros.cef?.inverters || [];
  let calculated = 0;
  let hasPvStrings = false;
  let complete = true;
  for (const inverter of inverters) {
    if (inverter.battery_only || inverter.no_panels || String(inverter.kind || inverter.type || "").toLocaleLowerCase("ro-RO").includes("invertor de baterie (ac)")) continue;
    const count = Math.max(1, number(inverter.count || inverter.quantity) || 1);
    const strings = (inverter.strings || []).filter((string) => number(string.panels) > 0);
    if (!strings.length) continue;
    hasPvStrings = true;
    for (const string of strings) {
      const stringModel = String(string.panel_model || "").trim().toLocaleLowerCase("ro-RO");
      const inverterModel = String(inverter.panel_model || "").trim().toLocaleLowerCase("ro-RO");
      const sameModel = !stringModel || (inverterModel && stringModel === inverterModel);
      const panelW = number(string.panel_w) || (sameModel ? number(inverter.panel_w) : 0);
      if (!panelW) {
        complete = false;
        continue;
      }
      calculated += number(string.panels) * panelW * count / 1000;
    }
  }
  if (hasPvStrings) {
    if (complete && calculated > 0) return Number(calculated.toFixed(3));
    return pros.cef?.total_kwp || pros.panel_kwp || pros._kwp || "";
  }
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

const ATR_BOARD_STATUSES = ["În lucru", "Generată", "Depusă", "Completări cerute", "ATR emis"];

function atrBoardStatus(item) {
  const saved = String(item?.workflow_status || "").trim();
  if (ATR_BOARD_STATUSES.includes(saved)) return saved;
  const tracked = String(item?.atr_track?.status || "").trim().toLocaleLowerCase("ro-RO");
  const trackedStages = {
    "trimis": "Depusă",
    "înregistrat": "Depusă",
    "completări solicitate": "Completări cerute",
    "dosar complet": "Depusă",
    "aviz emis": "ATR emis",
  };
  if (trackedStages[tracked]) return trackedStages[tracked];
  const legacy = String(item?.status || "").trim();
  return ATR_BOARD_STATUSES.includes(legacy) ? legacy : "În lucru";
}

function prosumerBoardStatus(item) {
  return String(item?.workflow_status || item?.status || item?.operator_stage || "Dosar în pregătire").trim();
}

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

const PROSUMER_STAGE_ACTIONS = {
  "Dosar în pregătire": "Completează documentele și verifică dosarul înainte de depunere",
  "Gata de depunere": "Depune dosarul la operatorul de distribuție",
  "Depus la operatorul de distribuție": "Urmărește cererea și eventualele solicitări de completare",
  "Aviz tehnic emis": "Verifică ATR-ul și pregătește contractul de racordare",
  "Programat pentru montaj": "Confirmă programarea instalării",
  "Montaj efectuat": "Programează verificările și probele PIF",
  "Probe și punere în funcțiune": "Finalizează documentele PIF și transmite ce solicită operatorul",
};

const PROSUMER_GUIDED_STEPS = [
  ["dossier-section-client", "1. Client și loc de consum"],
  ["dossier-section-installation", "2. Instalația"],
  ["dossier-section-acts", "3. Acte și responsabili"],
  ["dossier-section-documents", "4. Documente și semnare"],
  ["dossier-section-submission", "5. Depunere și distribuitor"],
  ["dossier-section-commissioning", "6. Punere în funcțiune"],
];

function prosumerWorkflowProgress(form, checklist) {
  const text = (value) => String(value ?? "").trim();
  const status = text(form?.workflow_status || form?.status);
  const completed = [
    Boolean(text(form?.client_name) && text(form?.address) && text(form?.pod) && text(form?.operator)),
    checklist ? checklist.installation : installationIsConfigured(form?.cef),
    Boolean(checklist?.acts && (text(form?.assigned_to) || text(form?.signers?.executant))),
    checklist ? checklist.documents : Boolean(form?.finalized),
    Boolean(text(form?.operator_stage) || (status && status !== "Dosar în pregătire")),
    checklist ? checklist.commissioning : Boolean(text(form?.commissioning_date || form?.pif_date) && text(form?.grounding_ohm)),
  ];
  const nextIndex = Math.max(0, completed.findIndex((done) => !done));
  return { completed, count: completed.filter(Boolean).length, nextIndex };
}

function ProsumerStepStatus({ complete, testId }) {
  return <span className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold"
    style={complete
      ? { background: "#eaf7ef", color: "#18894f" }
      : { background: "#fff4e8", color: "#c97922" }}
    data-testid={testId}>{complete ? "Complet" : "De completat"}</span>;
}

function prosumerRecommendedAction(item) {
  const status = prosumerBoardStatus(item);
  return PROSUMER_STAGE_ACTIONS[status] || "";
}

function atrEquipmentSummary(item, prosumers) {
  const pros = resolveLinkedProsumer(item, prosumers || []).linked;
  if (!pros) return [];
  const inverters = pros.cef?.inverters || [];
  const inverterModels = [...new Set(inverters.map((inv) => inv.brand_model || inv.model).filter(Boolean))];
  const panelModels = [...new Set(inverters.map((inv) => inv.panel_model).filter(Boolean))];
  const batteryModels = [...new Set([
    ...inverters.filter((inv) => inv.battery_mode === "own").map((inv) => inv.battery?.model),
    ...(pros.cef?.shared_batteries || []).map((battery) => battery.model),
  ].filter(Boolean))];
  const inverterKw = inverters.reduce((sum, inv) => sum + (Number(inv.p_nom_kw || inv.p_max_kw) || 0) * Math.max(1, Number(inv.count || inv.quantity) || 1), 0);
  const batteryKwh = inverters.filter((inv) => inv.battery_mode === "own").reduce((sum, inv) => {
    const battery = inv.battery || {};
    return sum + (Number(battery.capacity_kwh || battery.kwh) || 0) * Math.max(1, Number(battery.modules || battery.count) || 1) * Math.max(1, Number(inv.count || inv.quantity) || 1);
  }, 0) + (pros.cef?.shared_batteries || []).reduce((sum, battery) => sum + (Number(battery.capacity_kwh || battery.kwh) || 0) * Math.max(1, Number(battery.modules || battery.count) || 1), 0);
  const panelKwp = installedPanelKwp(pros);
  return [
    inverterModels.length ? `Invertor: ${inverterModels.join(", ")}${inverterKw ? ` · ${Number(inverterKw.toFixed(2))} kW` : ""}` : "",
    panelModels.length ? `Panouri: ${panelModels.join(", ")}${panelKwp ? ` · ${panelKwp} kWp` : ""}` : "",
    batteryModels.length ? `Baterie: ${batteryModels.join(", ")}${batteryKwh ? ` · ${Number(batteryKwh.toFixed(2))} kWh` : ""}` : "",
  ].filter(Boolean);
}
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
  const [dossierChecklist, setDossierChecklist] = useState(null);
  useEffect(() => { setDossierChecklist(null); }, [editId]);
  const [diuPre, setDiuPre] = useState(false);
  const [prosPre, setProsPre] = useState(false);
  const [catalogImportsBusy, setCatalogImportsBusy] = useState(false);
  const [sectionSaving, setSectionSaving] = useState(false);
  const [statusSavingId, setStatusSavingId] = useState("");
  const [draggedItemId, setDraggedItemId] = useState("");
  const [dropTargetStatus, setDropTargetStatus] = useState("");
  const ignoreAtrClickAfterDrop = useRef(false);

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
   …24501 tokens truncated…er((item) => item.battery_mode === "own" && item.battery?.model)
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
                  {isDeer && (() => {
                    const largePower = /(?:>|peste\s*)\s*400\s*kw/i.test(String(it.deer_case || it.request_type || ""));
                    const path = "/official-docx";
                    const name = largePower ? "Fisa_precompletare_DEER_peste_400_kW.pdf" : "Anexa_DEER_completata_" + it.id.slice(0, 8) + ".docx";
                    return <button type="button" className="col-span-2 min-h-10 rounded-lg border px-3 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + path, name)}>{largePower ? "Descarcă fișa de precompletare DEER (>400 kW)" : "Descarcă Anexa DEER completată"}</button>;
                  })()}
                </div>
              </article>;
            })}
          </div>}
          <div className={["prosumator", "atr"].includes(key) && recordsView === "board" ? "hidden" : (["clients", "prosumator", "atr", "pram"].includes(key) ? "hidden overflow-x-auto sm:block" : "overflow-x-auto")}>
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
                      const panels = [...new Set(inverters.flatMap((x) => x.battery_only || x.no_panels ? [] : (x.strings || []).map((row) => row.panel_model || x.panel_model)).filter(Boolean))];
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
                      {key === "atr" && <span className="inline-flex items-center flex-wrap gap-1 mr-1"><button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile("/atr/" + it.id + "/pdf?full=0")} title="Descarcă separat cererea ATR în PDF">PDF cerere ATR</button><button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/package.zip", "Pachet_ATR.zip")} title="Pachet ZIP cu PDF-ul ATR și anexa oficială disponibilă pentru operatorul selectat">PDF + anexele disponibile (ZIP)</button>{/deer|distributie energie electrica romania/i.test(String(it.operator || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")) && (() => {
                        const largePower = /(?:>|peste\s*)\s*400\s*kw/i.test(String(it.deer_case || it.request_type || ""));
                        const name = largePower ? "Fisa_precompletare_DEER_peste_400_kW.pdf" : "Anexa_DEER_completata_" + it.id.slice(0, 8) + ".docx";
                        return <button type="button" className="inline-flex rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile("/atr/" + it.id + "/official-docx", name)} title={largePower ? "Fișă de lucru precompletată; formularul oficial DEER original se află în pachetul ZIP" : "Descarcă formularul oficial DEER precompletat cu datele cunoscute din dosar"}>{largePower ? "Fișă DEER >400 kW (PDF)" : "Anexa DEER completată (DOCX)"}</button>;
                      })()}</span>}
                      {key === "prosumator" && (() => {
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
                      {key === "pram" && <button type="button" onClick={() => downloadAuthenticatedFile(`/pram/${encodeURIComponent(it.id)}/pdf`, `buletin_pram_${String(it.number || it.id).slice(0, 16)}.pdf`)} className="rounded border px-2 py-1 text-[11px] font-semibold" style={{ borderColor: "var(--line)", color: "var(--blue)" }} title="Descarcă PDF PRAM" data-testid={`pram-pdf-${it.id}`}>PDF</button>}
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




