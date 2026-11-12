import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, CircleDot, Clock3, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";

const MILESTONES = [
  ["dossier_generated", "Dosar generat"],
  ["dossier_submitted", "Dosar depus"],
  ["atr_received", "ATR emis"],
  ["atr_paid", "Factură ATR plătită"],
  ["installation_completed", "Instalație montată"],
  ["pif_started", "Probe / PIF începute"],
  ["prosumer_active", "Prosumator activ"],
  ["connection_certificate", "Certificat de racordare emis"],
  ["pif_signed", "PIF semnat"],
];

const localDateTime = (value) => {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.valueOf()) ? value : d.toLocaleString("ro-RO");
};

export function DossierTimeline({ id }) {
  const [data, setData] = useState({ events: [], blocker: { active: false } });
  const [note, setNote] = useState("");
  const [blocker, setBlocker] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data: result } = await api.get(`/prosumator/${id}/timeline`);
      setData({ events: result.events || [], blocker: result.blocker || { active: false } });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Jurnalul dosarului nu s-a putut încărca");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const addEvent = async (type, details = {}) => {
    setSaving(true);
    try {
      await api.post(`/prosumator/${id}/timeline`, { type, ...details });
      await load();
      if (type === "note" || type === "od_response" || type === "od_clarification") setNote("");
      if (type === "blocker_opened" || type === "od_clarification") { setBlocker(""); setDueDate(""); }
      toast.success(type === "blocker_resolved" ? "Blocaj rezolvat" : "Jurnal actualizat");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Evenimentul nu s-a putut salva");
    } finally { setSaving(false); }
  };

  return (
    <section className="mt-5 space-y-4" data-testid="dossier-timeline">
      <div className="rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }}>
        <div className="flex items-start justify-between gap-3">
          <div><h3 className="font-bold">Jurnalul dosarului</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Înregistrează evenimentele; etapele se actualizează automat.</p></div>
          <button type="button" className="rounded-lg p-2 hover:bg-white" onClick={load} aria-label="Reîncarcă jurnalul"><RefreshCw size={15} /></button>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {MILESTONES.map(([type, label]) => <button key={type} type="button" disabled={saving} onClick={() => addEvent(type)} className="flex items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2.5 text-left text-xs font-semibold hover:border-blue-300 disabled:opacity-50" style={{ borderColor: "var(--line)" }} data-testid={`timeline-${type}`}>
            <span>{label}</span><Plus size={14} style={{ color: "var(--blue)" }} />
          </button>)}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
          <h4 className="text-sm font-bold">Notă / apel / clarificare</h4>
          <textarea className="den-input mt-3" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Adaugă un detaliu util pentru echipă…" maxLength={1200} data-testid="timeline-note" />
          <div className="mt-2 flex flex-wrap gap-2">
            <Btn disabled={saving || !note.trim()} onClick={() => addEvent("note", { note: note.trim() })}><Plus size={14} /> Înregistrează nota</Btn>
            <Btn variant="secondary" disabled={saving || !note.trim() || data.blocker?.active} onClick={() => addEvent("od_clarification", { note: note.trim(), due_date: dueDate })}><AlertTriangle size={14} /> Clarificări cerute de OD</Btn>
            <Btn variant="secondary" disabled={saving} onClick={() => addEvent("od_response", { note: note.trim() })}><Check size={14} /> Răspuns trimis la OD</Btn>
          </div>
          <label className="mt-2 block text-xs" style={{ color: "var(--muted)" }}>Termen clarificare (opțional)<input className="den-input mt-1" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></label>
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: data.blocker?.active ? "#f1b8b8" : "var(--line)", background: data.blocker?.active ? "#fff8f7" : "white" }}>
          <h4 className="flex items-center gap-2 text-sm font-bold"><AlertTriangle size={15} style={{ color: data.blocker?.active ? "#b33333" : "var(--muted)" }} /> Blocaj</h4>
          {data.blocker?.active ? <>
            <p className="mt-2 text-sm font-semibold">{data.blocker.title}</p>
            {data.blocker.due_date && <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Termen: {data.blocker.due_date}</p>}
            <Btn className="mt-3" disabled={saving} onClick={() => addEvent("blocker_resolved")}><Check size={14} /> Marchează rezolvat</Btn>
          </> : <>
            <input className="den-input mt-3" value={blocker} onChange={(e) => setBlocker(e.target.value)} placeholder="Ce blochează dosarul?" maxLength={500} data-testid="timeline-blocker-title" />
            <label className="mt-2 block text-xs" style={{ color: "var(--muted)" }}>Termen (opțional)<input className="den-input mt-1" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></label>
            <Btn variant="secondary" className="mt-3" disabled={saving || !blocker.trim()} onClick={() => addEvent("blocker_opened", { note: blocker.trim(), due_date: dueDate })}><AlertTriangle size={14} /> Înregistrează blocajul</Btn>
          </>}
        </div>
      </div>

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
        <h4 className="mb-3 flex items-center gap-2 text-sm font-bold"><Clock3 size={15} /> Istoric ({data.events.length})</h4>
        {data.events.length ? <ol className="space-y-3">
          {[...data.events].reverse().map((event) => <li key={event.id} className="flex gap-3 text-xs" data-testid="timeline-event">
            <CircleDot size={14} className="mt-0.5 shrink-0" style={{ color: "var(--blue)" }} />
            <div className="min-w-0"><b>{event.label}</b>{event.note && <span> · {event.note}</span>}{event.from_status !== event.to_status && event.to_status && <span> · Etapă: {event.to_status}</span>}<div className="mt-0.5" style={{ color: "var(--muted)" }}>{localDateTime(event.at)}{event.by ? ` · ${event.by}` : ""}</div></div>
          </li>)}
        </ol> : <p className="text-xs" style={{ color: "var(--muted)" }}>Nu există evenimente în jurnal.</p>}
      </div>
    </section>
  );
}

