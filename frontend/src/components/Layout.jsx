import { useState } from "react";
import { Outlet, Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { BrandMark } from "@/components/BrandMark";
import { Menu, Home, FolderOpen, Receipt, Cpu, MoreHorizontal, UserRound, FileCheck2, CircuitBoard, Wrench, Globe } from "lucide-react";

export default function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const workflowPaths = ["/clienti", "/prosumator", "/cerere-atr", "/spor-putere", "/diu", "/catalog-echipamente", "/dosare-anre", "/mono", "/portaluri-distribuitori"];
  const showWorkflow = workflowPaths.some((path) => location.pathname.startsWith(path));
  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg)" }}>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="mobile-app-header md:hidden sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b">
          <button data-testid="menu-btn" onClick={() => setOpen(true)} aria-label="Deschide meniul"><Menu size={22} /></button>
          <BrandMark size={30} />
          <span className="font-extrabold tracking-wide">DNS ENERGY</span>
        </header>
        <main className="flex-1 px-4 sm:px-6 lg:px-9 py-6 lg:py-8 max-w-[1200px] w-full mx-auto pb-24 md:pb-8">
          <PlanBanner />
          {showWorkflow && <DossierWorkflow pathname={location.pathname} />}
          <Outlet />
        </main>
        <nav aria-label="Navigare rapidă" className="mobile-bottom-nav md:hidden fixed bottom-0 inset-x-0 z-20 grid grid-cols-5 border-t bg-white/95 backdrop-blur px-1 pt-2 pb-[max(8px,env(safe-area-inset-bottom))] shadow-[0_-4px_16px_rgba(20,35,70,0.08)]">
          <MobileNavItem to="/" icon={Home} label="Acasă" />
          <MobileNavItem to="/prosumator" icon={FolderOpen} label="Dosare" />
          <MobileNavItem to="/oferte" icon={Receipt} label="Oferte" />
          <MobileNavItem to="/catalog-echipamente" icon={Cpu} label="Catalog" />
          <button type="button" onClick={() => setOpen(true)} aria-label="Mai multe module" className="flex flex-col items-center justify-center gap-1 min-w-0 py-1 text-[10px] font-semibold" style={{ color: "var(--muted)" }}>
            <MoreHorizontal size={20} />
            <span>Mai mult</span>
          </button>
        </nav>
      </div>
    </div>
  );
}

const DOSSIER_STEPS = [
  { to: "/clienti", label: "Client", icon: UserRound, matches: ["/clienti"] },
  { to: "/prosumator", label: "Prosumator", icon: FolderOpen, matches: ["/prosumator"] },
  { to: "/cerere-atr", label: "ATR / spor", icon: FileCheck2, matches: ["/cerere-atr", "/spor-putere"] },
  { to: "/diu", label: "DI-U", icon: Wrench, matches: ["/diu"] },
  { to: "/catalog-echipamente", label: "Echipamente", icon: Cpu, matches: ["/catalog-echipamente"] },
  { to: "/dosare-anre", label: "Dosar ANRE", icon: FileCheck2, matches: ["/dosare-anre"] },
  { to: "/mono", label: "Schemă · PRAM", icon: CircuitBoard, matches: ["/mono"] },
  { to: "/portaluri-distribuitori", label: "Portal OD", icon: Globe, matches: ["/portaluri-distribuitori"] },
];

function DossierWorkflow({ pathname }) {
  return (
    <nav aria-label="Ordinea dosarului" className="mb-6 rounded-xl border bg-white p-3 sm:p-4" style={{ borderColor: "var(--line)" }} data-testid="dossier-workflow-nav">
      <div className="mb-2 px-1 text-[10px] font-bold uppercase tracking-[.14em]" style={{ color: "var(--muted)" }}>Flux de lucru · deschide direct un pas</div>
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
        {DOSSIER_STEPS.map(({ to, label, icon: Icon, matches }, index) => {
          const active = matches.some((path) => pathname.startsWith(path));
          return <li key={to} className="min-w-0">
            <NavLink to={to} aria-current={active ? "step" : undefined} className="flex min-h-10 min-w-0 items-center gap-2 rounded-lg border px-2.5 py-2 text-xs font-semibold transition hover:border-blue-300" style={active
              ? { background: "#eaf1ff", borderColor: "var(--blue)", color: "var(--blue)" }
              : { background: "#fff", borderColor: "var(--line)", color: "#475569" }}>
              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold" style={active ? { background: "var(--blue)", color: "#fff" } : { background: "#f1f5f9", color: "#475569" }}>{index + 1}</span>
              <Icon size={14} aria-hidden="true" />{label}
            </NavLink>
          </li>;
        })}
      </ol>
    </nav>
  );
}

function MobileNavItem({ to, icon: Icon, label }) {
  return (
    <Link to={to} className="flex flex-col items-center justify-center gap-1 min-w-0 py-1 text-[10px] font-semibold" style={{ color: "var(--muted)" }}>
      <Icon size={20} />
      <span className="truncate max-w-full">{label}</span>
    </Link>
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
    <div className="flex flex-wrap items-start justify-between gap-4 mb-7">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>{eyebrow}</div>
        <h1 className="text-3xl sm:text-4xl font-extrabold mt-1" style={{ color: "var(--ink)" }}>{title}</h1>
        {sub && <p className="text-sm mt-2 max-w-2xl" style={{ color: "var(--muted)" }}>{sub}</p>}
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
