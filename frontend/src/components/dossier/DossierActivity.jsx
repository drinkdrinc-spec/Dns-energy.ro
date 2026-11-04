import { useEffect, useMemo, useState } from "react";
import { Activity } from "lucide-react";
import { api } from "@/lib/api";

export function DossierActivity({ dossierId, workflowHistory }) {
  const [rows, setRows] = useState([]);
  const stableHistory = useMemo(() => Array.isArray(workflowHistory) ? workflowHistory : [], [workflowHistory]);
  useEffect(() => {
    let active = true;
    const load = async () => {
      const [auditResult, signingResult] = await Promise.allSettled([
        api.get("/audit", { params: { module: "prosumator", item_id: dossierId } }),
        api.get("/sign/requests", { params: { module: "prosumator", dossier_id: dossierId } }),
      ]);
      if (!active) return;
      const events = [];
      if (auditResult.status === "fulfilled") {
        (auditResult.value.data || []).forEach((item, index) => events.push({
          id: `audit-${item.at || index}-${index}`, at: item.at, title: item.action || "Actualizare dosar",
          detail: [item.user, ...(item.fields || [])].filter(Boolean).join(" · "),
        }));
      }
      if (signingResult.status === "fulfilled") {
        (signingResult.value.data || []).forEach((request) => (request.history || []).forEach((item, index) => events.push({
          id: `sign-${request.id}-${item.at || index}-${index}`, at: item.at,
          title: item.action || "Activitate de semnare", detail: request.doc_title || "Document din dosar",
        })));
      }
      stableHistory.forEach((item, index) => events.push({
        id: `flow-${item.at || index}-${index}`, at: item.at,
        title: `Stadiu: ${item.from || "—"} → ${item.to || "—"}`, detail: item.by || "",
      }));
      events.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
      setRows(events.slice(0, 30));
    };
    load();
    return () => { active = false; };
  }, [dossierId, stableHistory]);

  return <section className="mt-4 rounded-xl border bg-white p-4" style={{ borderColor: "var(--line)" }} data-testid="dossier-activity">
    <div className="flex items-center gap-2"><Activity size={16} style={{ color: "var(--blue)" }} /><h3 className="text-sm font-bold">Jurnalul dosarului</h3><span className="ml-auto text-[11px]" style={{ color: "var(--muted)" }}>{rows.length} evenimente</span></div>
    <ol className="mt-3 max-h-72 space-y-2 overflow-y-auto" data-testid="dossier-activity-list">
      {!rows.length && <li className="rounded-lg p-3 text-xs" style={{ background: "#f8fafd", color: "var(--muted)" }}>Nu există încă activitate înregistrată.</li>}
      {rows.map((item) => <li key={item.id} className="flex gap-3 rounded-lg border p-3" style={{ borderColor: "var(--line)" }}>
        <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--blue)" }} />
        <div className="min-w-0 flex-1"><div className="flex flex-wrap justify-between gap-2 text-xs"><b>{item.title}</b><time style={{ color: "var(--muted)" }}>{item.at ? new Date(item.at).toLocaleString("ro-RO") : ""}</time></div>
          {item.detail && <p className="mt-1 break-words text-[11px] leading-4" style={{ color: "var(--muted)" }}>{item.detail}</p>}</div>
      </li>)}
    </ol>
    <p className="mt-2 text-[10px] leading-4" style={{ color: "var(--muted)" }}>Jurnalul combină modificările dosarului, schimbările de etapă și evenimentele linkurilor de semnare.</p>
  </section>;
}

