import { useState } from "react";
import { Outlet, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { BrandMark } from "@/components/BrandMark";
import { Menu, Home, FolderKanban, ContactRound, BookOpen } from "lucide-react";
import { NavLink } from "react-router-dom";

export default function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg)" }}>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden sticky top-0 z-20 flex h-[54px] items-center gap-3 px-4 text-white shadow-sm" style={{ background: "var(--navy)" }}>
          <button data-testid="menu-btn" onClick={() => setOpen(true)} className="grid h-9 w-9 place-items-center rounded-lg hover:bg-white/10"><Menu size={21} /></button>
          <BrandMark size={29} />
          <span className="font-extrabold tracking-wide text-[15px]">D-ENERGY</span>
        </header>
        <main className="flex-1 px-4 sm:px-6 lg:px-9 pt-5 pb-24 md:py-7 max-w-[1200px] w-full mx-auto">
          <PlanBanner />
          <Outlet />
        </main>
        <nav className="den-mobile-nav md:hidden fixed bottom-0 inset-x-0 z-20 grid grid-cols-4 border-t px-2 pt-1.5 pb-[max(.45rem,env(safe-area-inset-bottom))]" aria-label="Navigare principală">
          {[["/", "Acasă", Home], ["/prosumator", "Dosare", FolderKanban], ["/clienti", "Contacte", ContactRound], ["/catalog", "Catalog", BookOpen]].map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `flex flex-col items-center justify-center gap-0.5 rounded-lg py-1 text-[10px] font-semibold transition-colors ${isActive ? "den-mobile-active" : "den-mobile-inactive"}`} data-testid={`mobile-nav-${label.toLowerCase()}`}><Icon size={18} strokeWidth={2.1} /><span>{label}</span></NavLink>)}
        </nav>
      </div>
    </div>
  );
}

function PlanBanner() {
  const { user } = useAuth();
  const p = user?.plan;
  if (!p || p.exempt || p.active) return null;
  return (
    <div className="mb-5 rounded-xl px-4 py-3 text-sm flex flex-wrap items-center gap-3" style={{ background: "#fff8e6", color: "#8a5a00" }} data-testid="plan-banner">
      <b>Abonament: {p.status}.</b> {p.policy === "blocked" ? "Accesul la module este blocat" : "Puteți consulta datele, dar nu puteți crea sau modifica dosare"} — datele sunt păstrate în siguranță.
      {user.account_type !== "team" && <Link to="/abonament" className="font-bold underline" data-testid="plan-banner-link">Activează abonamentul</Link>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, sub, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 mb-5 sm:mb-7">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>{eyebrow}</div>
        <h1 className="text-[22px] sm:text-3xl font-extrabold mt-1" style={{ color: "var(--ink)" }}>{title}</h1>
        {sub && <p className="text-xs sm:text-sm mt-1.5 max-w-2xl" style={{ color: "var(--muted)" }}>{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function Btn({ children, variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "text-white shadow-[0_4px_12px_#2878f022]",
    secondary: "bg-white border",
    danger: "",
  };
  const bg = { primary: { background: "var(--blue)" }, secondary: { color: "#31425c", borderColor: "var(--line)" }, danger: { background: "#fff0f0", color: "#b33333" } };
  return (
    <button
      {...props}
      style={bg[variant]}
      className={`inline-flex items-center gap-2 rounded-[9px] px-4 py-2.5 text-[12px] font-bold transition hover:brightness-95 disabled:opacity-60 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
