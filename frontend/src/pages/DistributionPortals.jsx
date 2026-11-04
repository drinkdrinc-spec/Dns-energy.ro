import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, ShieldCheck, Search, AlertTriangle, CheckCircle2, Archive, MessageSquare, Paperclip, Send, Clock3 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Btn } from "@/components/Layout";
import { api, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";

const MESSAGE_STATUSES = ["Nou", "În lucru", "Răspuns OD primit", "Închis"];
const EMPTY_MESSAGE = { direction: "Primit", subject: "", message: "", message_date: new Date().toISOString().slice(0, 10), response_due: "", status: "Nou" };

const PORTALS = [
  { id: "deer", name: "DEER", detail: "Distribuție Energie Electrică România", url: "https://avize.distributie-energie.ro/", hints: ["5940"] },
  { id: "delgaz", name: "Delgaz Grid", detail: "Portal clienți și racordare", url: "https://delgaz.ro/login", hints: ["EMO3"] },
  { id: "oltenia", name: "Distribuție Oltenia", detail: "Portal DEO Connect", url: "https://portal.distributieoltenia.ro/", hints: [] },
  { id: "retele", name: "Rețele Electrice România", detail: "Muntenia, Banat și Dobrogea", url: "https://contulmeu.reteleelectrice.ro/", hints: ["RO001E", "RO002E", "RO005E"] },
];

// Regional links and county groups are taken from DEER's June 2025 user guide.
const DEER_REGIONS = [
  { url: "https://avize.edtn.ro/", counties: ["Cluj", "Bihor", "Maramureș", "Satu-Mare", "Bistrița-Năsăud", "Sălaj"] },
  { url: "https://avize.sdeets.ro/", counties: ["Alba", "Brașov", "Covasna", "Harghita", "Mureș", "Sibiu"] },
  { url: "https://avize.edmn.ro/", counties: ["Brăila", "Buzău", "Dâmbovița", "Galați", "Prahova", "Vrancea"] },
];
const normalizeCounty = (value) => String(value || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/^jud(?:etul)?\.?\s*/, "").replace(/\s+/g, " ").trim();
const deerRegionalPortal = (county) => {
  const key = normalizeCounty(county);
  return DEER_REGIONS.find((region) => region.counties.some((name) => normalizeCounty(name) === key))?.url || null;
};

function detectOperator(value) {
  const pod = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!pod) return { pod, match: null, message: "Introdu POD-ul pentru a identifica operatorul." };
  if (/^RO001E/.test(pod) || /^RO002E/.test(pod) || /^RO005E/.test(pod)) {
    return { pod, match: "retele", message: "Prefix POD recunoscut pentru Rețele Electrice. Verifică și județul de pe factură." };
  }
  if (/^EMO3/.test(pod)) return { pod, match: "delgaz", message: "Prefix POD recunoscut pentru Delgaz Grid. Verifică operatorul de pe factură." };
  if (/^5940\d{14}$/.test(pod)) return { pod, match: "deer", message: "Format POD posibil asociat DEER. Confirmă sucursala și operatorul din factură." };
  return { pod, match: null, message: "Nu pot confirma operatorul doar din acest POD. Alege operatorul indicat pe factura de energie." };
}

function operatorId(value) {
  const operator = String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (/deer|distributie energie electrica/.test(operator)) return "deer";
  if (/delgaz/.test(operator)) return "delgaz";
  if (/oltenia|deo connect/.test(operator)) return "oltenia";
  if (/retele electrice|e-distribu/.test(operator)) return "retele";
  return "";
}

export default function DistributionPortals() {
  const [pros, setPros] = useState([]);
  const [atrCases, setAtrCases] = useState([]);
  const [powerCases, setPowerCases] = useState([]);
  const [prosId, setProsId] = useState("");
  const [pod, setPod] = useState("");
  const [manual, setManual] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messageSaving, setMessageSaving] = useState(false);
  const [messageForm, setMessageForm] = useState(EMPTY_MESSAGE);
  const [messageFiles, setMessageFiles] = useState([]);
  useEffect(() => {
    Promise.allSettled([api.get("/data/prosumator"), api.get("/data/atr"), api.get("/data/power")]).then((results) => {
      const [prosResult, atrResult, powerResult] = results;
      if (prosResult.status === "fulfilled") setPros(Array.isArray(prosResult.value.data) ? prosResult.value.data : []);
      else setLoadFailed(true);
      if (atrResult.status === "fulfilled") setAtrCases(Array.isArray(atrResult.value.data) ? atrResult.value.data : []);
      if (powerResult.status === "fulfilled") setPowerCases(Array.isArray(powerResult.value.data) ? powerResult.value.data : []);
    });
  }, []);
  const selectedPros = pros.find((item) => item.id === prosId) || null;
  useEffect(() => {
    if (!selectedPros?.id) { setMessages([]); return undefined; }
    let active = true;
    setMessagesLoading(true);
    api.get("/data/documents?q=" + encodeURIComponent(selectedPros.id)).then(({ data }) => {
      if (!active) return;
      const rows = (Array.isArray(data) ? data : []).filter((item) => item.kind === "operator_message" && item.dossier_id === selectedPros.id);
      rows.sort((a, b) => String(b.message_date || b.created_at || "").localeCompare(String(a.message_date || a.created_at || "")));
      setMessages(rows);
    }).catch(() => { if (active) setMessages([]); })
      .finally(() => { if (active) setMessagesLoading(false); });
    return () => { active = false; };
  }, [selectedPros?.id]);
  const result = useMemo(() => detectOperator(pod), [pod]);
  const selectedId = manual || result.match || operatorId(selectedPros?.operator);
  const selected = PORTALS.find((p) => p.id === selectedId);
  // Only explicitly linked records are offered for download; never infer a dossier from a shared name.
  const linkedAtr = atrCases.filter((item) => selectedPros && item.pros_id === selectedPros.id);
  const linkedPower = powerCases.filter((item) => selectedPros && item.pros_id === selectedPros.id);
  // DEER routes all new applications through the unified dedicated portal.
  // Legacy regional portals remain useful only for historical records.
  const historicalPortalUrl = selectedId === "deer" ? deerRegionalPortal(selectedPros?.county) : null;
  const portalUrl = selected?.url;
  const powerIncrease = /spor de putere/i.test(String(selectedPros?.request_type || ""));
  const atrCreateUrl = selectedPros?.client_id
    ? `/cerere-atr?new=atr&clientId=${encodeURIComponent(selectedPros.client_id)}&prosId=${encodeURIComponent(selectedPros.id)}${powerIncrease ? "&case=power-increase" : ""}`
    : "";

  const saveOperatorMessage = async (event) => {
    event.preventDefault();
    if (!selectedPros) return toast.error("Selectează dosarul pentru care notezi corespondența.");
    if (!messageForm.subject.trim() || !messageForm.message.trim()) return toast.error("Completează subiectul și mesajul.");
    setMessageSaving(true);
    try {
      const attachments = [];
      for (const file of messageFiles) {
        const form = new FormData();
        form.append("file", file);
        const { data } = await api.post("/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
        attachments.push({ storage_path: data.storage_path, original_filename: data.original_filename, content_type: data.content_type, size: data.size });
      }
      const operatorName = selectedPros.operator || selectedPros.operator_name || selected?.name || "Operator neconfirmat";
      const title = `[dosar:${selectedPros.id}] ${messageForm.direction} — ${messageForm.subject.trim()}`;
      const { data: createdMessage } = await api.post("/data/documents", {
        kind: "operator_message",
        doc_type: "Corespondență operator",
        title,
        client_name: selectedPros.client_name || "",
        client_id: selectedPros.client_id || "",
        dossier_id: selectedPros.id,
        operator: operatorName,
        pod: selectedPros.pod || pod || "",
        direction: messageForm.direction,
        subject: messageForm.subject.trim(),
        message: messageForm.message.trim(),
        message_date: messageForm.message_date,
        response_due: messageForm.response_due,
        status: messageForm.status,
        source: "Înregistrat manual din portalul operatorului",
        attachments,
      });
      toast.success("Corespondența a fost salvată în dosar.");
      setMessageForm({ ...EMPTY_MESSAGE, message_date: new Date().toISOString().slice(0, 10) });
      setMessageFiles([]);
      const input = document.getElementById("operator-message-files");
      if (input) input.value = "";
      setMessages((current) => [createdMessage, ...current].sort((a, b) => String(b.message_date || b.created_at || "").localeCompare(String(a.message_date || a.created_at || ""))));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Corespondența nu a putut fi salvată.");
    } finally {
      setMessageSaving(false);
    }
  };

  const updateMessageStatus = async (item, status) => {
    try {
      const { data } = await api.put("/data/documents/" + encodeURIComponent(item.id), { ...item, status });
      setMessages((current) => current.map((row) => row.id === item.id ? data : row));
      toast.success("Starea mesajului a fost actualizată.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Starea mesajului nu a putut fi actualizată.");
    }
  };

  const selectPros = (id) => {
    setProsId(id);
    const item = pros.find((entry) => entry.id === id);
    if (!item) {
      setPod("");
      setManual("");
      return;
    }
    setPod(item.pod || "");
    // Keep manual as an explicit user override only; otherwise derive the
    // portal from the current POD and fall back to the dossier's operator.
    setManual("");
  };

  return (
    <div>
      <PageHeader eyebrow="RACORDARE" title="Portaluri distribuitori" sub="Selectează dosarul clientului sau introdu POD-ul pentru a deschide portalul distribuitorului potrivit." />
      <section className="den-panel mb-6">
        <div className="den-field mb-4">
          <label htmlFor="portal-client">Dosar de prosumator</label>
          <select id="portal-client" className="den-input w-full" value={prosId} onChange={(e) => selectPros(e.target.value)} data-testid="portal-pros-select">
            <option value="">Selectează un dosar (opțional)...</option>
            {pros.filter((item) => !/\bTEST\b/i.test([item.number, item.client_name].filter(Boolean).join(" "))).map((item) => (
              <option key={item.id} value={item.id}>{item.client_name || "Client"} — {item.address || item.pod || item.id.slice(0, 6)}</option>
            ))}
          </select>
          {loadFailed && <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Lista dosarelor nu s-a încărcat; poți introduce POD-ul manual.</div>}
        </div>
        {selectedPros && <div className="mb-4 rounded-lg border bg-white px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid="portal-selected-dossier">
          <b>{selectedPros.client_name || "Client"}</b> · {selectedPros.operator || "operator neconfirmat"} · POD {selectedPros.pod || "necompletat"}
        </div>}
        <label className="block text-sm font-bold mb-2" htmlFor="portal-pod">POD-ul locului de consum</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input id="portal-pod" className="den-input flex-1" value={pod} onChange={(e) => { setPod(e.target.value); setManual(""); }} placeholder="Introdu POD-ul de pe factură" autoComplete="off" />
          <Btn variant="secondary" onClick={() => { setPod(""); setManual(""); setProsId(""); }}>Șterge</Btn>
        </div>
        <div className="flex gap-2 items-start mt-3 text-sm" style={{ color: result.match ? "var(--ink)" : "var(--muted)" }}>
          {result.match ? <CheckCircle2 size={18} className="shrink-0 mt-0.5" /> : <AlertTriangle size={18} className="shrink-0 mt-0.5" />}
          <span>{result.message}</span>
        </div>
        <div className="mt-4">
          <label className="block text-sm font-bold mb-2" htmlFor="portal-manual">Confirmă operatorul de pe factură</label>
          <select id="portal-manual" className="den-input w-full" value={manual} onChange={(e) => setManual(e.target.value)}>
            <option value="">Folosește sugestia după POD</option>
            {PORTALS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        {selected && (
          <div className="mt-5 p-4 rounded-xl border" style={{ borderColor: "var(--line)", background: "var(--bg)" }}>
            <div className="font-bold">{selected.name}</div>
            <div className="text-sm mt-1" style={{ color: "var(--muted)" }}>{selected.detail}</div>
            {selectedId === "deer" && <div className="text-xs mt-2" style={{ color: "var(--muted)" }}>Pentru cereri și documente noi, DEER indică portalul dedicat unificat. Portalurile regionale vechi sunt doar pentru consultarea istoricului.</div>}
            {atrCreateUrl && <Link to={atrCreateUrl} className="inline-flex items-center gap-2 mt-4 rounded-lg border px-4 py-3 text-sm font-bold" style={{ borderColor: "var(--blue)", color: "var(--blue)", background: "#fff" }} data-testid="portal-create-prefilled-atr"><CheckCircle2 size={16} /> Pregătește cererea ATR din acest dosar</Link>}
            {selectedPros && <div className="mt-4 rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }} data-testid="portal-dossier-shortcuts">
              <div className="font-bold text-sm">Dosar gata de verificat și depus</div>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Descarcă documentele DNS Energy, apoi atașează-le în portalul oficial. Datele și fișierele rămân în dosarul clientului.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => openAuthenticatedFile(`/dossier/${selectedPros.id}/export`)}>Previzualizează dosarul PDF</button>
                <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/sld/${selectedPros.id}/pdf?download=1`, `schema_monofilara_${selectedPros.id.slice(0, 8)}.pdf`)}>Descarcă schema</button>
                <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/docs/buletin_priza/${selectedPros.id}`, `pram_priza_${selectedPros.id.slice(0, 8)}.pdf`)}>Descarcă PRAM</button>
                <button type="button" className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/docs/pv_pif/${selectedPros.id}`, `pif_${selectedPros.id.slice(0, 8)}.pdf`)}>Descarcă PIF</button>
                {linkedAtr.map((item) => <button type="button" key={item.id} className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/atr/${item.id}/package.zip`, `pachet_ATR_${item.number || item.id.slice(0, 8)}.zip`)} data-testid="portal-atr-package"><Archive size={13} className="inline mr-1" /> Pachet ATR {item.number || item.client_name || ""}</button>)}
                {linkedPower.map((item) => <button type="button" key={item.id} className="rounded-lg border px-3 py-2 text-xs font-semibold" style={{ borderColor: "var(--line)" }} onClick={() => downloadAuthenticatedFile(`/power/${item.id}/package.zip`, `pachet_spor_putere_${item.number || item.id.slice(0, 8)}.zip`)} data-testid="portal-power-package"><Archive size={13} className="inline mr-1" /> Pachet spor {item.number || item.client_name || ""}</button>)}
                {!linkedAtr.length && !linkedPower.length && <span className="text-xs basis-full" style={{ color: "var(--muted)" }} data-testid="portal-no-linked-package">Nu există încă o cerere ATR sau de spor legată explicit de acest dosar. Creeaz-o din butonul „Pregătește cererea ATR”.</span>}
              </div>
            </div>}
            <a href={portalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-4 ml-2 rounded-lg px-4 py-3 text-sm font-bold text-white" style={{ background: "var(--blue)" }} data-testid="portal-open-selected">
              <ExternalLink size={16} /> Deschide portalul operatorului
            </a>
            {historicalPortalUrl && <a href={historicalPortalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-4 ml-2 rounded-lg border px-4 py-3 text-sm font-semibold" style={{ borderColor: "var(--line)" }}>Portal regional istoric · {selectedPros?.county || "zona DEER"} ↗</a>}
            <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>Portalul se deschide într-o filă separată. Autentificarea rămâne în browserul folosit la conectare, atât timp cât portalul își menține sesiunea. DNS Energy nu stochează parola portalului.</p>
          </div>
        )}
      </section>
      {selectedPros && <section className="den-panel mt-5" style={{ borderColor: "var(--line)" }} data-testid="operator-message-log">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="font-bold text-sm"><MessageSquare size={15} className="inline mr-2" />Corespondență cu operatorul</h3>
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Notează mesajele și răspunsurile consultate în portal. Înregistrarea este manuală; DNS Energy nu importă automat mesajele OD.</p>
                </div>
                <span className="text-xs font-semibold rounded-full px-2 py-1" style={{ background: "var(--bg)" }}>{messages.length} înregistrări</span>
              </div>
              <form className="mt-4 grid sm:grid-cols-2 gap-3" onSubmit={saveOperatorMessage}>
                <div className="den-field"><label>Direcție</label><select className="den-input" value={messageForm.direction} onChange={(e) => setMessageForm((v) => ({ ...v, direction: e.target.value }))}><option>Primit</option><option>Trimis</option></select></div>
                <div className="den-field"><label>Data mesajului</label><input className="den-input" type="date" value={messageForm.message_date} onChange={(e) => setMessageForm((v) => ({ ...v, message_date: e.target.value }))} /></div>
                <div className="den-field sm:col-span-2"><label>Subiect *</label><input className="den-input" value={messageForm.subject} maxLength={180} onChange={(e) => setMessageForm((v) => ({ ...v, subject: e.target.value }))} placeholder="Ex.: Solicitare completare documente" required /></div>
                <div className="den-field sm:col-span-2"><label>Mesaj / observații *</label><textarea className="den-input" rows={3} maxLength={8000} value={messageForm.message} onChange={(e) => setMessageForm((v) => ({ ...v, message: e.target.value }))} placeholder="Notează conținutul relevant și acțiunea cerută." required /></div>
                <div className="den-field"><label>Termen de răspuns</label><input className="den-input" type="date" value={messageForm.response_due} onChange={(e) => setMessageForm((v) => ({ ...v, response_due: e.target.value }))} /></div>
                <div className="den-field"><label>Stare</label><select className="den-input" value={messageForm.status} onChange={(e) => setMessageForm((v) => ({ ...v, status: e.target.value }))}>{MESSAGE_STATUSES.map((status) => <option key={status}>{status}</option>)}</select></div>
                <div className="den-field sm:col-span-2"><label><Paperclip size={13} className="inline mr-1" />Documente atașate</label><input id="operator-message-files" className="den-input" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx" onChange={(e) => setMessageFiles(Array.from(e.target.files || []).slice(0, 8))} /><span className="text-[11px]" style={{ color: "var(--muted)" }}>Maximum 8 fișiere pentru fiecare mesaj.</span></div>
                <div className="sm:col-span-2"><Btn type="submit" disabled={messageSaving || messagesLoading}><Send size={14} />{messageSaving ? "Se salvează..." : "Salvează în dosar"}</Btn></div>
              </form>
              <div className="mt-4 space-y-2">
                {messagesLoading && <p className="text-xs" style={{ color: "var(--muted)" }}>Se încarcă istoricul...</p>}
                {!messagesLoading && !messages.length && <p className="rounded-lg p-3 text-xs" style={{ background: "var(--bg)", color: "var(--muted)" }}>Nu există încă mesaje înregistrate pentru acest dosar.</p>}
                {messages.map((item) => <article key={item.id} className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid={"operator-message-"+item.id}>
                  <div className="flex flex-wrap items-start gap-2"><div className="flex-1 min-w-[180px]"><b className="text-sm">{item.subject}</b><div className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>{item.direction} · {item.operator} · {item.message_date || "Dată neprecizată"}{item.response_due ? ` · termen ${item.response_due}` : ""}</div></div>
                    <select className="den-input !py-1 !text-xs w-full sm:w-auto" value={item.status || "Nou"} onChange={(e) => updateMessageStatus(item, e.target.value)} aria-label={"Stare mesaj " + item.subject}>{MESSAGE_STATUSES.map((status) => <option key={status}>{status}</option>)}</select>
                  </div>
                  <p className="mt-2 text-sm whitespace-pre-wrap">{item.message}</p>
                  {!!item.attachments?.length && <div className="mt-2 flex flex-wrap gap-2">{item.attachments.map((file, index) => <button type="button" key={file.storage_path || index} className="text-xs underline" onClick={() => openAuthenticatedFile("/files/" + file.storage_path)}>{file.original_filename || "Atașament"}</button>)}</div>}
                </article>)}
              </div>
            </section>}
      <div className="flex items-start gap-3 text-sm p-4 rounded-xl" style={{ background: "#eef6ff", color: "#25456e" }}>
        <ShieldCheck size={20} className="shrink-0 mt-0.5" />
        <div><b>Protecția contului</b><p className="mt-1">Nu introduce parola distribuitorului în DNS Energy. Conectarea și depunerea au loc pe portalul oficial al operatorului.</p></div>
      </div>
      <h2 className="text-lg font-bold mt-7 mb-3">Portaluri oficiale</h2>
      <div className="grid md:grid-cols-2 gap-3">
        {PORTALS.map((p) => (
          <div key={p.id} className="den-panel">
            <div className="font-bold">{p.name}</div>
            <div className="text-sm mt-1 mb-4" style={{ color: "var(--muted)" }}>{p.detail}</div>
            <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-bold underline" style={{ color: "var(--blue)" }}>Deschide portalul <ExternalLink size={14} /></a>
          </div>
        ))}
      </div>
    </div>
  );
}
