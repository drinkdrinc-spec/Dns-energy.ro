import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";
import { CalendarClock } from "lucide-react";

const tone = (r) => (r.days_left == null ? ["#f3f4f6", "#6b7280", "fără termen"] : r.days_left < 0 ? ["#fff0f0", "#9b2c2c", `depășit cu ${-r.days_left} zile`]
  : r.days_left <= r.remind_days ? ["#fff8e6", "#8a5a00", `${r.days_left} zile`] : ["#ecfdf3", "#166534", `${r.days_left} zile`]);

export function AtrDeadlines() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const ok = can(user, "atr") && (user?.plan?.exempt || user?.plan?.features?.includes("*") || user?.plan?.features?.includes("atr"));
  useEffect(() => { if (ok) api.get("/atr/deadlines").then((r) => setRows(r.data)).catch(() => setRows([])); }, [ok]);
  if (!ok || !rows) return null;
  const late = rows.filter((r) => r.days_left != null && r.days_left < 0).length;
  return (
    <div className="den-panel mb-6" data-testid="atr-deadlines-panel">
      <div className="flex items-center gap-2 mb-3"><CalendarClock size={16} style={{ color: "var(--blue)" }} /><b className="text-sm">Termene cereri ATR active</b>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{rows.length} active{late ? ` · ${late} depășite` : ""}</span>
        <Link to="/cerere-atr" className="ml-auto text-xs font-bold" style={{ color: "var(--blue)" }} data-testid="atr-deadlines-all">Toate cererile →</Link></div>
      {!rows.length ? <div className="text-xs" style={{ color: "var(--muted)" }} data-testid="atr-deadlines-empty">Nicio cerere ATR activă (trimisă și fără aviz emis).</div> :
        <div className="divide-y" style={{ borderColor: "var(--line)" }}>{rows.map((r) => { const c = tone(r); return (
          <Link key={r.id} to={`/cerere-atr?edit=${r.id}`} className="flex flex-wrap items-center gap-3 py-2 text-xs hover:bg-[#f6f9ff]" data-testid={`atr-deadline-${r.id}`}>
            <b className="min-w-[160px]">{r.client_name}{r.is_test ? " (TEST)" : ""}</b><span style={{ color: "var(--muted)" }}>{r.operator}</span>
            <span>{r.status}{r.reg_no ? ` · nr. ${r.reg_no}` : ""}</span>
            <span className="ml-auto">{r.due_kind ? `${r.due_kind}: ${new Date(r.due).toLocaleDateString("ro-RO")}` : "așteaptă nr. de înregistrare"}</span>
            <span className="font-bold rounded-full px-2 py-0.5" style={{ background: c[0], color: c[1] }}>{c[2]}</span>
          </Link>); })}</div>}
    </div>
  );
}
