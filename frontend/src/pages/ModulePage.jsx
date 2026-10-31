import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X } from "lucide-react";
import { toast } from "sonner";
import { AiImportButton, GeneratedDocs } from "@/components/ProsumatorTools";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs } from "@/components/dossier/ClientDocs";
import { SignRequests } from "@/components/sign/SignRequests";
import { SldPanel } from "@/components/sld/SldPanel";
import { TestDossierButtons } from "@/components/sld/TestDossier";
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
        setRefOptions((prev) => ({ ...prev, [ref]: r.data.map((x) => ({ ...x, id: x.id, label: MODULES[ref].display(x) })) }));
      }).catch(() => {});
    });
    // eslint-disable-next-line
  }, [key]);

  const openNew = () => { setForm(key === "atr" ? { date: new Date().toISOString().slice(0, 10) } : {}); setEditId(null); setChecks({}); };
  const openEdit = (item) => { setForm({ ...item }); setEditId(item.id); setChecks(item.checklist || {}); };
  const setVal = (name, value) => {
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
    const payload = { ...form };
    if (cfg.checklist) payload.checklist = checks;
    try {
      if (editId) await api.put(`/data/${key}/${editId}`, payload);
      else if (key === "prosumator") await api.post("/import/prosumator", payload);
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

  const filtered = useMemo(() => {
    if (!q) return items;
    const ql = q.toLowerCase();
    return items.filter((i) => JSON.stringify(i).toLowerCase().includes(ql));
  }, [items, q]);

  const checkedCount = cfg.checklist ? cfg.checklist.filter((c) => checks[c]).length : 0;

  return (
    <div>
      <PageHeader eyebrow={cfg.eyebrow} title={cfg.title} sub={cfg.sub}
        action={<div className="flex gap-2 flex-wrap">
          {key === "prosumator" && <TestDossierButtons onDone={load} />}
          {key === "prosumator" && <AiImportButton onExtracted={(d) => { setForm((prev) => { if (!prev || editId) return d; const next = { ...prev }; for (const [k, v] of Object.entries(d || {})) { if (k === "files" || v == null || v === "") continue; if (next[k] == null || next[k] === "") next[k] = v; } next.files = [...(prev.files || []), ...(d.files || [])].filter((x, i, a) => a.findIndex((y) => (y.storage_path || y.original_filename) === (x.storage_path || x.original_filename)) === i); return next; }); setEditId(null); setChecks({}); }} />}
          <Btn data-testid="add-btn" onClick={form ? () => setForm(null) : openNew}>{form ? <><X size={15} /> Închide</> : <><Plus size={15} /> {cfg.addLabel}</>}</Btn>
        </div>} />

      {form && (
        <div className="den-panel mb-6" data-testid="module-form">
          <h2 className="text-lg font-bold mb-5">{editId ? "Editează înregistrarea" : cfg.addLabel}</h2>
          {key === "prosumator" ? <ProsumatorQuickForm cfg={cfg} form={form} setVal={setVal} refOptions={refOptions} /> : key === "atr" ? <AtrQuickForm cfg={cfg} form={form} setVal={(name, value) => {
            if (name === "client_name") {
              const client = (refOptions.clients || []).find((x) => x.label === value);
              setForm((prev) => ({
                ...prev, client_name: value,
                ...(client ? { pod: prev.pod || client.pod || "", operator: client.operator || prev.operator || "", address: prev.address || client.address || "", cf_nr: prev.cf_nr || client.cf_nr || "", cadastral_nr: prev.cadastral_nr || client.cadastral_nr || "", applicant_type: prev.applicant_type || client.kind || "", object_name: prev.object_name || client.name || value } : {}),
              }));
            } else if (name === "deer_case") {
              const mappedRequest = {
                "Loc nou de consum și producere — Anexa 1": "utilizator nou definitiv",
                "Loc existent — notificare — Anexa 2": "modificarea elementelor de natură tehnică fără depășirea puterii aprobate anterior",
                "Loc existent prosumator — actualizare CRR — Anexa 3": "modificarea elementelor de natură administrativă fără depășirea puterii aprobate anterior",
                "Loc existent — spor de putere — Anexa 1": "dezvoltarea unui utilizator existent (spor de putere)",
                "Prosumator prin program de finanțare — Anexa 4": "utilizator nou definitiv",
                "Loc existent ≤10,8 kW — notificare simplificată — Anexa 5": "modificarea elementelor de natură tehnică fără depășirea puterii aprobate anterior",
              }[value];
              setForm((prev) => ({ ...prev, deer_case: value, ...(mappedRequest ? { request_type: mappedRequest } : {}) }));
            } else setVal(name, value);
          }} refOptions={refOptions} /> : (
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
          <h2 className="text-lg font-bold">Înregistrări salvate <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>({items.length})</span></h2>
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
