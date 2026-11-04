import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Mail, Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Btn, PageHeader } from "@/components/Layout";

const SOURCES = [
  ["prosumator", "Dosar prosumator", "/prosumator"],
  ["atr", "Cerere ATR", "/cerere-atr"],
  ["power", "Spor de putere", "/spor-putere"],
  ["diu", "Dosar DI-U", "/diu"],
];
const STATUSES = ["Nou", "În lucru", "Răspuns transmis", "Rezolvat"];
const EMPTY = { direction: "Primit de la OD", operator: "", subject: "", reference: "", message_type: "Solicitare", received_at: new Date().toISOString().slice(0, 10), status: "Nou", next_action: "", next_action_due: "", content: "", dossier_ref: "" };

const dateLabel = (value) => {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("ro-RO");
};

export default function OperatorMessages() {
  const [items, setItems] = useState([]);
  const [dossiers, setDossiers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setBusy(true);
    setError("");
    const [messages, ...records] = await Promise.allSettled([
      api.get("/data/operator_messages"),
      ...SOURCES.map(([module]) => api.get(`/data/${module}`)),
    ]);
    if (messages.status === "fulfilled") setItems(Array.isArray(messages.value.data) ? messages.value.data : []);
    else setError(messages.reason?.response?.data?.detail || "Nu am putut încărca registrul de mesaje OD.");
    const all = records.flatMap((result, index) => result.status === "fulfilled"
      ? (Array.isArray(result.value.data) ? result.value.data : []).map((record) => ({
        ...record, _module: SOURCES[index][0], _label: SOURCES[index][1], _path: SOURCES[index][2],
      })) : []);
    setDossiers(all.filter((record) => !record.is_test && !/^TEST\b/i.test(`${record.client_name || ""} ${record.number || ""}`)));
    setBusy(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("ro-RO");
    return [...items].sort((a, b) => String(b.received_at || b.created_at || "").localeCompare(String(a.received_at || a.created_at || "")))
      .filter((item) => (statusFilter === "all" || item.status === statusFilter)
        && (!needle || [item.operator, item.subject, item.reference, item.client_name, item.content, item.next_action].filter(Boolean).join(" ").toLocaleLowerCase("ro-RO").includes(needle)));
  }, [items, query, statusFilter]);

  const selectDossier = (value) => {
    const record = dossiers.find((entry) => `${entry._module}:${entry.id}` === value);
    setForm((current) => ({
      ...current, dossier_ref: value,
      ...(record ? { operator: current.operator || record.operator || record.operator_name || record.distributor || "", client_name: record.client_name || record.company?.name || "", dossier_module: record._module, dossier_id: record.id, dossier_kind: record._label } : { client_name: "", dossier_module: "", dossier_id: "", dossier_kind: "" }),
    }));
  };

  const save = async (event) => {
    event.preventDefault();
    if (!form.operator.trim() || !form.subject.trim()) return;
    const { dossier_ref, ...payload } = form;
    setBusy(true);
    setError("");
    try {
      await api.post("/data/operator_messages", payload);
      setForm({ ...EMPTY, received_at: new Date().toISOString().slice(0, 10) });
      setOpen(false);
      toast.success("Mesajul OD a fost adăugat în registru.");
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Mesajul nu a putut fi salvat.");
    } finally { setBusy(false); }
  };

  const updateStatus = async (item, status) => {
    try {
      await api.put(`/data/operator_messages/${encodeURIComponent(item.id)}`, { ...item, status });
      setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, status } : entry));
    } catch (err) {
      setError(err.response?.data?.detail || "Nu am putut actualiza statusul mesajului.");
    }
  };

  return <div>
    <PageHeader eyebrow="RACORDARE · URMĂRIRE" title="Corespondență OD" sub="Păstrează mesajele operatorului lângă dosarul clientului și urmărește răspunsurile, termenele și pașii următori."
      action={<div className="flex gap-2"><Btn variant="secondary" onClick={load} disabled={busy} aria-label="Reîncarcă mesajele"><RefreshCw size={15} /> Reîncarcă</Btn><Btn onClick={() => setOpen((value) => !value)}><Plus size={15} /> Mesaj nou</Btn></div>} />
    <div className="mb-5 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "#cfe0f8", background: "#f3f8ff", color: "#294567" }}>
      <Mail size={18} className="mt-0.5 shrink-0" /><div><b>Registru de corespondență</b><p className="mt-1">În această versiune, mesajele se introduc manual din e-mailul sau portalul OD. DNS Energy nu citește automat contul de e-mail și nu păstrează parola portalului. Pentru depunere, deschide portalul oficial.</p><Link to="/portaluri-distribuitori" className="mt-2 inline-flex items-center gap-1 font-bold underline">Portaluri distribuitori <ExternalLink size={13} /></Link></div>
    </div>

    {error && <div className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{error}</div>}

    {open && <form onSubmit={save} className="den-panel mb-5" data-testid="operator-message-form">
      <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-bold">Adaugă corespondență</h2><button type="button" className="text-sm font-semibold underline" onClick={() => setOpen(false)}>Închide</button></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Direcție"><select className="den-input" value={form.direction} onChange={(event) => setForm({ ...form, direction: event.target.value })}><option>Primit de la OD</option><option>Trimis către OD</option></select></Field>
        <Field label="Operator de distribuție *"><input className="den-input" required value={form.operator} onChange={(event) => setForm({ ...form, operator: event.target.value })} placeholder="ex. DEER — Transilvania Nord" /></Field>
        <Field label="Tip"><select className="den-input" value={form.message_type} onChange={(event) => setForm({ ...form, message_type: event.target.value })}>{["Solicitare", "Răspuns", "Notificare", "Document lipsă", "Programare", "Altele"].map((type) => <option key={type}>{type}</option>)}</select></Field>
        <Field label="Subiect *"><input className="den-input" required maxLength={180} value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} /></Field>
        <Field label="Număr de înregistrare / referință"><input className="den-input" maxLength={100} value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} /></Field>
        <Field label="Data mesajului"><input className="den-input" type="date" value={form.received_at} onChange={(event) => setForm({ ...form, received_at: event.target.value })} /></Field>
        <Field label="Leagă de un dosar"><select className="den-input" value={form.dossier_ref} onChange={(event) => selectDossier(event.target.value)}><option value="">Fără dosar asociat</option>{dossiers.map((record) => <option key={`${record._module}:${record.id}`} value={`${record._module}:${record.id}`}>{record._label} · {record.client_name || record.company?.name || "Client"}{record.number ? ` · ${record.number}` : ""}</option>)}</select></Field>
        <Field label="Următorul pas"><input className="den-input" maxLength={180} value={form.next_action} onChange={(event) => setForm({ ...form, next_action: event.target.value })} placeholder="ex. Trimite documentul solicitat" /></Field>
        <Field label="Termen"><input className="den-input" type="date" value={form.next_action_due} onChange={(event) => setForm({ ...form, next_action_due: event.target.value })} /></Field>
        <Field label="Status"><select className="den-input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select></Field>
        <label className="den-field sm:col-span-2 lg:col-span-3"><span>Conținut / observații</span><textarea className="den-input min-h-28" maxLength={8000} value={form.content} onChange={(event) => setForm({ ...form, content: event.target.value })} placeholder="Notează mesajul sau ce a solicitat operatorul. Verifică datele înainte de a le salva." /></label>
      </div>
      <div className="mt-4 flex justify-end"><Btn type="submit" disabled={busy || !form.operator.trim() || !form.subject.trim()}><Plus size={15} /> Salvează mesajul</Btn></div>
    </form>}

    <section className="den-panel" aria-label="Mesaje de la operatori">
      <div className="mb-4 flex flex-wrap gap-2">
        <label className="relative min-w-[220px] flex-1"><Search size={15} className="absolute left-3 top-3" style={{ color: "var(--muted)" }} /><input className="den-input pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Caută operator, client, referință…" aria-label="Caută în corespondența OD" /></label>
        <select className="den-input w-full sm:w-auto" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filtrează după status"><option value="all">Toate statusurile</option>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select>
      </div>
      {busy && !items.length ? <p className="py-8 text-center text-sm" style={{ color: "var(--muted)" }}>Se încarcă registrul…</p> : filtered.length ? <div className="space-y-3">
        {filtered.map((item) => {
          const dossierSource = SOURCES.find(([module]) => module === item.dossier_module);
          return <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }} data-testid={`operator-message-${item.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-bold text-blue-800">{item.direction || "Primit de la OD"}</span><span className="text-xs" style={{ color: "var(--muted)" }}>{item.message_type || "Mesaj"} · {dateLabel(item.received_at)}</span></div><h2 className="mt-2 text-base font-bold">{item.subject}</h2><p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{item.operator}{item.reference ? ` · Ref. ${item.reference}` : ""}</p></div><select className="den-input !w-auto min-w-[145px] !py-2 text-xs font-semibold" aria-label={`Status ${item.subject}`} value={STATUSES.includes(item.status) ? item.status : "Nou"} onChange={(event) => updateStatus(item, event.target.value)}>{STATUSES.map((status) => <option key={status}>{status}</option>)}</select></div>
            {item.content && <p className="mt-3 whitespace-pre-wrap text-sm">{item.content}</p>}
            {(item.next_action || item.next_action_due) && <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950"><b>Următorul pas:</b> {item.next_action || "—"}{item.next_action_due ? ` · termen ${dateLabel(item.next_action_due)}` : ""}</div>}
            {item.dossier_id && dossierSource && <Link className="mt-3 inline-flex text-sm font-bold underline" to={`${dossierSource[2]}?edit=${encodeURIComponent(item.dossier_id)}`}>{item.dossier_kind || dossierSource[1]} · {item.client_name || "Deschide dosarul"}</Link>}
          </article>;
        })}
      </div> : <div className="py-10 text-center"><Mail size={30} className="mx-auto mb-2" style={{ color: "var(--muted)" }} /><p className="text-sm font-semibold">{items.length ? "Nu am găsit mesaje pentru filtrul selectat." : "Registrul este gol."}</p><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Înregistrează un e-mail sau un răspuns primit pe portalul operatorului.</p></div>}
    </section>
  </div>;
}

function Field({ label, children }) {
  return <label className="den-field"><span>{label}</span>{children}</label>;
}

