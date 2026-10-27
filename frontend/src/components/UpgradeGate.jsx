import { Link } from "react-router-dom";
import { Lock } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";
import { Btn } from "@/components/Layout";

const NEED = { prosumator: "START, PRO sau FULL", diu: "PRO sau FULL" };

export function Gate({ feat, children }) {
  const { user } = useAuth();
  if (can(user, feat)) return children;
  const p = user.plan;
  return (
    <div className="den-panel max-w-2xl" data-testid="upgrade-gate">
      <div className="flex items-center gap-3"><span className="grid place-items-center w-11 h-11 rounded-xl" style={{ background: "#eef4ff" }}><Lock size={20} style={{ color: "var(--blue)" }} /></span>
        <div><div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>Modul indisponibil în abonamentul actual</div>
          <h2 className="text-xl font-extrabold">Este necesar abonamentul {NEED[feat] || "FULL"}</h2></div></div>
      <p className="text-sm mt-4" style={{ color: "var(--muted)" }}>
        {p.active ? `Abonamentul dvs. ${p.name} nu include acest modul.` : `Abonament: ${p.status}. Contul este blocat până la activarea unui abonament.`} Dosarele și documentele existente rămân salvate în siguranță.</p>
      <Link to="/abonament"><Btn className="mt-5" data-testid="upgrade-btn">Vezi abonamentele și treci la un plan superior</Btn></Link>
    </div>
  );
}
