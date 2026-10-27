import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AlertTriangle, ExternalLink } from "lucide-react";

export function FormAlert({ operator, scope }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { if (operator) api.get(`/forms/alerts?operator=${encodeURIComponent(operator)}&scope=${scope}`).then((r) => setRows(r.data)).catch(() => {}); else setRows([]); }, [operator, scope]);
  if (!rows.length) return null;
  return (
    <div className="rounded-xl px-4 py-3 mb-3 text-xs" style={{ background: "#fff8e6", color: "#8a5a00" }} data-testid={`form-alert-${scope}`}>
      <div className="font-bold flex items-center gap-1.5"><AlertTriangle size={14} />Formularul oficial al operatorului s-a schimbat sau nu mai este disponibil — verificați înainte de depunere</div>
      {rows.map((f) => <div key={f.id} className="mt-1">{f.title}: <b>{f.status}</b>{f.version ? ` (versiune confirmată: ${f.version})` : ""} ·{" "}
        <a href={f.url} target="_blank" rel="noopener noreferrer" className="underline font-bold inline-flex items-center gap-0.5">deschide formularul <ExternalLink size={10} /></a></div>)}
      <div className="mt-1">După verificare, confirmați noua versiune în Registrul formularelor oficiale.</div>
    </div>
  );
}
