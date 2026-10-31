import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, API, openAuthenticatedFile } from "@/lib/api";
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
  const [showTestRecords, setShowTestRecords] = useState(null);
  const [form, setForm] = useState(null); // null=hidden, {} = open
  const [editId, setEditId] = useState(null);
  const [checks, setChecks] = useState({});
  const [refOptions, setRefOptions] = useState({});
  const [q, setQ] = useState("");
  const [savedAt, setSavedAt] = useState(0);
  const [diuPre, setDiuPre] = useState(false);

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
        const rows = ref === "clients" ? r.data.filter((item) => !/\bTEST\b/i.test(String(item.name || ""))) : r.data;
        setRefOptions((prev) => ({ ...prev, [ref]: rows.map((x) => ({ ...x, id: x.id, label: MODULES[ref].display(x) })) }));
      }).catch(() => {});
    });
    if (key === "atr") api.get("/data/prosumator").then((r) => setRefOptions((prev) => ({ ...prev, prosumator: r.data || [] }))).catch(() => {});
    if (key === "atr") {
      const params = new URLSearchParams(window.location.search);
      const clientId = params.get("clientId");
      if (params.get("new") === "atr" && clientId) {
        Promise.all([api.get("/data/clients"), api.get("/data/prosumator")]).then(([clientsRes, prosRes]) => {
          const pros = (prosRes.data || []).find((item) => item.id === params.get("prosId") || item.client_id === clientId);
          const client = (clientsRes.data || []).find((item) => item.id === clientId)
            || (pros && (clientsRes.data || []).find((item) => String(item.name || "").trim().toLowerCase() === String(pros.client_name || "").trim().toLowerCase()));
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
              pv_kw: pros.inverter_kw || "", p_evac_kw: pros.power || "" } : {}),
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
    if (key === "clients" || key === "prosumator") {
      api.get("/data/prosumator").then((r) => setLinkedProsumer(r.data || [])).catch(() => {});
      api.get("/data/diu").then((r) => setLinkedDiu(r.data || [])).catch(() => {});
    }
    if (key === "diu") {
      const params = new URLSearchParams(window.location.search);
      const clientId = params.get("clientId");
      const prosId = params.get("prosId");
      if (params.get("new") === "diu" && clientId) {
        Promise.all([api.get("/data/clients"), prosId ? api.get("/data/prosumator") : Promise.resolve({ data: [] })]).then(([clientsRes, prosRes]) => {
          const client = (clientsRes.data || []).find((item) => item.id === clientId);
          const pros = (prosRes.data || []).find((item) => item.id === prosId);
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
        if (linked.inverter_kw) next.pv_kw = linked.inverter_kw;
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

  const remove = async (id) => {
    if (!window.confirm("Ștergi această înregistrare?")) return;
    await api.delete(`/data/${key}/${id}`);
    toast.success("Șters"); load();
  };

  const isTestRecord = (item) => /\bTEST\b/i.test([item.number, item.name, item.client_name, item.idcode].filter(Boolean).join(" "));
  const hiddenTestCount = ["clients", "prosumator", "diu"].includes(key) ? items.filter(isTestRecord).length : 0;
  const onlyTestRecords = items.length > 0 && items.every(isTestRecord);
  const visibleItems = showTestRecords === true || (showTestRecords === null && onlyTestRecords) ? items : (["clients", "prosumator", "diu"].includes(key) ? items.filter((item) => !isTestRecord(item)) : items);
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
          <Btn data-testid="add-btn" onClick={form ? () => setForm(null) : openNew}>{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> {cfg.addLabel}</>}</Btn>
        </div>} />

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
          {key === "prosumator" ? <ProsumatorQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : key === "atr" ? <AtrQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : (
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
          {key === "atr" && <AtrDossier id={editId} form={form} setVal={setVal} />}
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
            <Btn onClick={save} data-testid="save-btn">Salvează</Btn>
            <Btn variant="secondary" onClick={() => window.print()} data-testid="pdf-btn">Tipărește / PDF</Btn>
            <Btn variant="secondary" onClick={() => setForm(null)}>Anulează</Btn>
          </div>
        </div>
      )}

      <div className="den-panel">
        <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
          <h2 className="text-lg font-bold">Înregistrări salvate <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({visibleItems.length})</span></h2>
          {hiddenTestCount > 0 && <button type="button" className="text-xs underline" onClick={() => setShowTestRecords((value) => !value)}>{(showTestRecords === true || (showTestRecords === null && onlyTestRecords)) ? "Ascunde" : "Arată"} înregistrările TEST ({hiddenTestCount})</button>}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input data-testid="search-input" className="den-input w-[240px]" style={{ paddingLeft: 34 }} placeholder="Caută..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-sm py-8 text-center rounded-lg" style={{ color: "var(--muted)", background: "var(--bg)" }}>Nu există înregistrări încă.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="items-table">
              <thead>
                <tr className="text-left" style={{ background: "#f8fafd", color: "var(--muted)" }}>
                  {cfg.columns.map((c) => <th key={c.key} className="px-3 py-2.5 font-semibold text-[12px] whitespace-nowrap">{c.label}</th>)}
                  <th className="px-3 py-2.5 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <tr key={it.id} className="border-t hover:bg-[#fafcff]" style={{ borderColor: "var(--line)" }}>
                    {cfg.columns.map((c) => <td key={c.key} className="px-3 py-3 whitespace-nowrap">{it[c.key] || "—"}</td>)}
                    <td className="px-2 py-3 text-left whitespace-normal sticky right-0 z-10 bg-white shadow-[-8px_0_10px_-10px_rgba(15,23,42,0.45)] max-w-[220px]">
                      {key === "clients" && (() => {
                        const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
                        const dossier = linkedProsumer.find((p) => p.client_id ? p.client_id === it.id : normalize(p.client_name) === normalize(it.name));
                        const diu = linkedDiu.find((d) => (d.client_id ? d.client_id === it.id : normalize(d.client_name) === normalize(it.name)) || (d.pros_id && d.pros_id === dossier?.id));
                        const linkClass = "inline-flex rounded border px-2 py-1 text-[11px] font-semibold mr-1";
                        const diuUrl = "/diu?new=diu&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "");
                        return <span className="inline-flex max-w-[204px] items-center flex-wrap gap-1">
                          <button type="button" className={linkClass} onClick={() => { window.location.href = diuUrl; }}>Creează DI-U</button>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "")}>Cerere ATR</a>
                          <a className={linkClass} href={"/cerere-atr?new=atr&clientId=" + encodeURIComponent(it.id) + (dossier ? "&prosId=" + encodeURIComponent(dossier.id) : "") + "&case=" + encodeURIComponent("Loc existent — spor de putere — Anexa 1")}>Spor de putere</a>
                          {dossier && <>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${dossier.id}/export`)}>Dosar PDF</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/sld/${dossier.id}/pdf`)}>Schemă</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${dossier.id}/pif/pdf`)}>PIF</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${dossier.id}/file/priza`)}>Buletin PRAM</button>
                          </>}
                          {diu && <>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`)}>PRAM priză</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_cont`)}>Continuitate</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_izol`)}>Izolație</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_ddr`)}>DDR</button>
                          </>}
                        </span>;
                      })()}
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
                          <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/sld/${it.id}/pdf`)}>Schemă</button>
                          <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/pif/pdf`)}>PV PIF</button>
                          <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/dossier/${it.id}/file/priza`)}>Buletin PRAM</button>
                          {diu && <>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_priza`)}>PRAM DI-U</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_cont`)}>Continuitate</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_izol`)}>Izolație</button>
                            <button type="button" className={linkClass} onClick={() => openAuthenticatedFile(`/diu/${diu.id}/pdf?doc=pram_ddr`)}>DDR</button>
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
        )}
      </div>
    </div>
  );
}
