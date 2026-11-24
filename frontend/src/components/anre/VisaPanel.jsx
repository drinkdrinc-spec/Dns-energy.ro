import { useEffect, useState } from "react";
import { FileSpreadsheet, Mail, Phone, Megaphone } from "lucide-react";
import { api, API } from "@/lib/api";
import { VisaEmailDialog } from "@/components/anre/VisaEmailDialog";
import { VisaCampaign } from "@/components/anre/VisaCampaign";
import { VisaCallDialog } from "@/components/anre/VisaCallDialog";

const col = (v) => (v.days_left < 0 ? "#9b2c2c" : v.days_left <= 30 ? "#8a5a00" : "#166534");
const dt = (s) => new Date(s).toLocaleDateString("ro-RO");

export function VisaPanel({ reloadKey }) {
  const [list, setList] = useState(null);
  const [mail, setMail] = useState(null);
  const [n, setN] = useState(0);
  const [camp, setCamp] = useState(false);
  const [call, setCall] = useState(null);
  const today = new Date().toISOString().slice(0, 10);
  useEffect(() => { api.get("/admin/operators/visas").then((r) => setList(r.data)); }, [reloadKey, n]);
  if (!list) return null;
  return (
    <div className="den-panel mb-4 overflow-x-auto" data-testid="visa-panel">
      <div className="flex items-center justify-between mb-1"><h3 className="font-bold">Vizări ANRE apropiate (90 de zile) și depășite</h3>
        <div className="flex gap-3"><button className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setCamp(true)} data-testid="visa-campaign-open"><Megaphone size={14} /> Campanie e-mail (30 zile)</button><a href={`${API}/admin/operators/visas.xlsx?auth=${localStorage.getItem("den_token")}`} className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid="visa-export-xlsx"><FileSpreadsheet size={14} /> Descarcă Excel</a></div></div>
      <table className="w-full text-xs"><thead><tr className="text-left" style={{ color: "var(--muted)" }}><th className="py-1">Firmă</th><th>Atestat</th><th>Data vizării</th><th>Termen</th><th>Contact</th><th>Memento / contact</th><th>Ultimul apel</th><th></th></tr></thead>
        <tbody>{list.map((v) => (
          <tr key={v.tenant} className="border-t" style={{ borderColor: "var(--line)", background: v.days_left < 0 ? "#fdecec" : undefined }} data-testid={`visa-row-${v.cui}`}>
            <td className="py-1.5"><b>{v.company}</b><div>CUI {v.cui}</div></td><td>nr. {v.attest_no || "—"}</td>
            <td>{dt(v.visa_date)}{!v.visa_confirmed && <div style={{ color: "#8a5a00" }}>neconfirmată</div>}</td>
            <td className="font-bold" style={{ color: col(v) }} data-testid={`visa-days-${v.cui}`}>{v.days_left < 0 ? `depășită cu ${-v.days_left} zile` : v.days_left === 0 ? "astăzi" : `în ${v.days_left} zile`}</td>
            <td>{v.contact_name}<div>{v.contact_email} {v.contact_phone}</div></td>
            <td>{v.visa_reminded_at ? `memento ${dt(v.visa_reminded_at)}` : "—"}{v.last_contact_at && <div data-testid={`visa-last-contact-${v.cui}`}>e-mail {dt(v.last_contact_at)}</div>}</td>
            <td data-testid={`visa-call-${v.cui}`}>{v.last_call ? <><b>{v.last_call.outcome}</b> · {dt(v.last_call.at)}{v.last_call.callback_date && <div style={{ color: v.last_call.callback_date <= today ? "#9b2c2c" : undefined, fontWeight: v.last_call.callback_date <= today ? 700 : 400 }}>revenire {dt(v.last_call.callback_date)}</div>}{v.last_call.note && <div className="truncate max-w-[160px]" title={v.last_call.note}>{v.last_call.note}</div>}</> : "—"}</td>
            <td className="space-y-1"><button className="font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setCall(v)} data-testid={`visa-call-btn-${v.cui}`}><Phone size={12} /> Apel</button><br /><button className="font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setMail(v)} disabled={!v.contact_email} data-testid={`visa-email-${v.cui}`}><Mail size={12} /> E-mail AI</button></td></tr>))}
          {!list.length && <tr><td colSpan={8} className="py-4 text-center" style={{ color: "var(--muted)" }}>Nicio vizare în următoarele 90 de zile.</td></tr>}</tbody></table>
      {camp && <VisaCampaign onClose={() => setCamp(false)} onSent={() => setN((x) => x + 1)} />}
      {call && <VisaCallDialog op={call} onClose={() => setCall(null)} onSaved={() => setN((x) => x + 1)} />}
      {mail && <VisaEmailDialog op={mail} onClose={() => setMail(null)} onSent={() => setN(n + 1)} />}
    </div>
  );
}
