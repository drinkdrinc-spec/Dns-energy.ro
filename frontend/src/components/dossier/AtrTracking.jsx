import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Send, CalendarClock } from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare");
const today = () => new Date().toISOString().slice(0, 10);
const fmt = (d) => (d ? new Date(d).toLocaleDateString("ro-RO") : "—");

function Due({ label, d, testid, warn = 3 }) {
  if (!d) return null;
  const left = Math.ceil((new Date(d) - new Date(today())) / 86400000);
  const c = left < 0 ? ["#fff0f0", "#9b2c2c", `depășit cu ${-left} zile`] : left <= warn ? ["#fff8e6", "#8a5a00", `${left} zile rămase`] : ["#ecfdf3", "#166534", `${left} zile rămase`];
  return <div className="rounded-lg px-3 py-2 text-xs" style={{ background: c[0], color: c[1] }} data-testid={testid}><b>{label}:</b> {fmt(d)} · {c[2]}</div>;
}

export function AtrTracking({ id, operator }) {
  const [t, setT] = useState(null);
  const [to, setTo] = useState("");
  const [f, setF] = useState({ reg_no: "", reg_date: today(), date: today(), atr_no: "", atr_date: today(), note: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/atr/${id}/track`).then((r) => setT(r.data)).catch(() => {});
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  useEffect(() => {
    api.get("/operator-contacts").then((r) => {
      const o = (operator || "").toLowerCase();
      const k = o.includes("delgaz") ? "delgaz" : o.includes("rețele") || o.includes("retele") ? "rer" : o.includes("oltenia") ? "oltenia" : "deer";
      setTo((v) => v || r.data.find((c) => c.op === k)?.email || "");
    });
  }, [operator]);
  const act = async (body, ok) => { try { const { data } = await api.post(`/atr/${id}/track`, body); setT(data); toast.success(ok); } catch (e) { err(e); } };
  const send = async () => {
    if (!window.confirm(`Se trimite dosarul ATR complet la ${to}, cu copie la dvs. Continuați?`)) return;
    setBusy(true);
    try { const { data } = await api.post(`/atr/${id}/submit`, { to }); setT(data.track); toast.success(data.sent_to ? `Trimis la ${data.sent_to}` : "Dosar TEST — e-mailul real nu a fost expediat"); } catch (e) { err(e); }
    setBusy(false);
  };
  if (!t) return null;
  const terms = t.terms || {};
  const inp = (k, type = "text", ph = "") => <input type={type} className="den-input" placeholder={ph} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`atr-track-${k}`} />;
  return (
    <div className="mt-5 rounded-xl border p-4" style={{ borderColor: "var(--line)" }} data-testid="atr-tracking">
      <div className="flex flex-wrap items-center gap-3 mb-3"><CalendarClock size={16} style={{ color: "var(--blue)" }} /><b className="text-sm">Depunere și termene</b>
        <span className="text-[11px] font-bold rounded-full px-2 py-0.5" style={{ background: "#eef4ff", color: "#1e40af" }} data-testid="atr-track-status">{t.status}</span>
        {t.reg_no && <span className="text-xs">Nr. înregistrare <b>{t.reg_no}</b> / {fmt(t.reg_date)}</span>}{t.atr_no && <span className="text-xs">ATR <b>{t.atr_no}</b> / {fmt(t.atr_date)}</span>}</div>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="den-field flex-1 min-w-[240px]"><label>Adresa distribuitorului (domeniu oficial)</label><input className="den-input" value={to} onChange={(e) => setTo(e.target.value)} data-testid="atr-send-to" /></div>
        <Btn type="button" onClick={send} disabled={busy || !to} data-testid="atr-send-btn"><Send size={14} />{busy ? "Se trimite…" : t.sent_at ? "Retrimite dosarul" : "Trimite dosarul la distribuitor"}</Btn>
      </div>
      {t.sent_at && <div className="text-[11px] mt-1" style={{ color: "var(--muted)" }} data-testid="atr-sent-info">Trimis la {t.sent_to} pe {new Date(t.sent_at).toLocaleString("ro-RO")} (link de descărcare valabil până la {fmt(t.token_exp)}).</div>}
      <div className="grid sm:grid-cols-2 gap-3 mt-4">
        <Due label="Termen verificare documentație" d={t.check_due} warn={terms.remind_days} testid="atr-due-check" /><Due label="Termen emitere aviz" d={t.issue_due} warn={terms.remind_days} testid="atr-due-issue" />
      </div>
      <div className="flex flex-wrap gap-2 items-end mt-3">
        <div className="den-field"><label>Nr. înregistrare primit</label>{inp("reg_no")}</div><div className="den-field"><label>Data înregistrării</label>{inp("reg_date", "date")}</div>
        <Btn type="button" variant="secondary" onClick={() => act({ action: "register", reg_no: f.reg_no, reg_date: f.reg_date }, "Înregistrare salvată")} data-testid="atr-register-btn">Salvează înregistrarea</Btn>
      </div>
      <div className="flex flex-wrap gap-2 items-end mt-3">
        <div className="den-field"><label>Data</label>{inp("date", "date")}</div>
        <Btn type="button" variant="secondary" onClick={() => act({ action: "complete", date: f.date }, "Dosar complet — termen aviz calculat")} data-testid="atr-complete-btn">Dosar declarat complet</Btn>
        <div className="den-field"><label>Completări cerute</label>{inp("note", "text", "ce a cerut distribuitorul")}</div>
        <Btn type="button" variant="secondary" onClick={() => act({ action: "incomplete", note: f.note }, "Salvat")} data-testid="atr-incomplete-btn">Completări solicitate</Btn>
        <div className="den-field"><label>Nr. aviz (ATR)</label>{inp("atr_no")}</div><div className="den-field"><label>Data avizului</label>{inp("atr_date", "date")}</div>
        <Btn type="button" onClick={() => act({ action: "issued", date: f.atr_date, atr_no: f.atr_no }, "Aviz înregistrat")} data-testid="atr-issued-btn">Aviz emis</Btn>
      </div>
      <details className="mt-3 text-xs"><summary className="cursor-pointer font-bold" data-testid="atr-terms-toggle">Termene standard: verificare {terms.check_days} zile lucrătoare · aviz {terms.issue_days} zile · reamintire cu {terms.remind_days} zile înainte</summary>
        <TermsEditor terms={terms} t={t} act={act} /></details>
      <div className="mt-3 text-[11px] space-y-0.5" data-testid="atr-events">{(t.events || []).slice().reverse().map((e, i) => <div key={i}><b>{new Date(e.at).toLocaleString("ro-RO")}</b> · {e.text}</div>)}</div>
    </div>
  );
}

function TermsEditor({ terms, t, act }) {
  const [v, setV] = useState({ ...terms, check_due: t.check_due || "", issue_due: t.issue_due || "" });
  const n = (k, l, type = "number") => <div className="den-field"><label>{l}</label><input type={type} className="den-input" value={v[k] || ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} data-testid={`atr-terms-${k}`} /></div>;
  return (
    <div className="flex flex-wrap gap-2 items-end mt-2">
      {n("check_days", "Verificare (zile lucr.)")}{n("issue_days", "Emitere aviz (zile)")}{n("remind_days", "Reamintire (zile înainte)")}
      <Btn type="button" variant="secondary" onClick={() => act({ action: "terms", check_days: v.check_days, issue_days: v.issue_days, remind_days: v.remind_days }, "Termene salvate")} data-testid="atr-terms-save">Salvează termenele</Btn>
      {n("check_due", "Termen verificare", "date")}{n("issue_due", "Termen aviz", "date")}
      <Btn type="button" variant="secondary" onClick={() => act({ action: "dates", check_due: v.check_due, issue_due: v.issue_due }, "Date modificate")} data-testid="atr-dates-save">Modifică datele</Btn>
    </div>
  );
}
