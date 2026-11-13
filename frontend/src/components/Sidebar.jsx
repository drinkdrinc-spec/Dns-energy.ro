import { useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { BrandMark } from "@/components/BrandMark";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert,
  FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, LogOut, X,
  Briefcase, ShieldCheck, PenLine, Lock, CreditCard, Receipt, Sparkles, ChevronDown, MapPin,
} from "lucide-react";
import { can, isOff, ROUTE_FEATURE } from "@/lib/plan";

const ICONS = { LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert, FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, Briefcase, ShieldCheck, PenLine, CreditCard, Receipt, Sparkles, MapPin };

const MAIN_NAV = [
  { to: "/", icon: "LayoutDashboard", text: "Tablou de bord", testid: "nav-home" },
  { to: "/simulare", icon: "SunMedium", text: "Proiectare", testid: "nav-project", badge: "BETA" },
  { to: "/prosumator", icon: "FolderOpen", text: "Dosare", testid: "nav-prosumator" },
  { to: "/harta", icon: "MapPin", text: "Hartă", testid: "nav-map" },
  { to: "/lucrari", icon: "Briefcase", text: "Lucrări", testid: "nav-works" },
  { to: "/clienti", icon: "Users", text: "Contacte", testid: "nav-clients" },
  { to: "/diu", icon: "FolderOpen", text: "Dosare DIU", testid: "nav-diu" },
  { to: "/cerere-atr", icon: "FileCheck2", text: "Cereri ATR", testid: "nav-atr" },
  { to: "/pram", icon: "FileCheck2", text: "Buletine PRAM", testid: "nav-pram" },
  { to: "/catalog-echipamente", icon: "Cpu", text: "Catalog", testid: "nav-equipment-catalog" },
  { to: "/setari", icon: "Settings", text: "Setări", testid: "nav-settings" },
];

const GROUPS = [
  { label: "Documente și tehnic", items: [
    { to: "/mono", icon: "GitBranch", text: "Scheme monofilare", testid: "nav-mono" },
    { to: "/tablouri", icon: "LayoutGrid", text: "Tablouri electrice", testid: "nav-panels" },
    { to: "/antiinsularizare", icon: "ShieldAlert", text: "Antiinsularizare", testid: "nav-anti" },
    { to: "/echipamente", icon: "Cpu", text: "Echipamente", testid: "nav-equipment" },
    { to: "/semnare", icon: "PenLine", text: "Semnare la distanță", testid: "nav-remote-signing" },
    { to: "/documente", icon: "Files", text: "Documente", testid: "nav-documents" },
    { to: "/formulare-oficiale", icon: "BookOpen", text: "Formulare oficiale", testid: "nav-forms" },
    { to: "/catalog", icon: "BookOpen", text: "Catalog tehnic", testid: "nav-catalog" },
  ]},
  { label: "Racordare și operatori", items: [
    { to: "/spor-putere", icon: "PlugZap", text: "Spor de putere / BMP", testid: "nav-power" },
    { to: "/distribuitori", icon: "Network", text: "Distribuitori", testid: "nav-operators" },
  ]},
  { label: "Oferte și contracte", items: [
    { to: "/oferte", icon: "Receipt", text: "Oferte de preț", testid: "nav-offers" },
    { to: "/contracte", icon: "FileCheck2", text: "Contracte", testid: "nav-contracts" },
    { to: "/asistent-ai", icon: "Sparkles", text: "Asistent AI", testid: "nav-ai-assistant" },
  ]},
  { label: "Administrare", items: [
    { to: "/utilizatori", icon: "ShieldCheck", text: "Utilizatori și roluri", testid: "nav-users", admin: true },
    { to: "/abonament", icon: "CreditCard", text: "Abonament și facturare", testid: "nav-subscription", owner: true },
    { to: "/atestat-anre", icon: "ShieldCheck", text: "Atestat ANRE firmă", testid: "nav-operator-attest", owner: true },
    { to: "/dosare-anre", icon: "Briefcase", text: "Dosare ANRE", testid: "nav-anre" },
    { to: "/abonamente-admin", icon: "Receipt", text: "Utilizatori și abonamente", testid: "nav-admin-billing", platform: true },
    { to: "/module-platforma", icon: "LayoutGrid", text: "Module platformă", testid: "nav-platform-modules", platform: true },
    { to: "/operatori-anre", icon: "ShieldCheck", text: "Operatori ANRE", testid: "nav-admin-operators", platform: true },
    { to: "/setari-baza", icon: "ShieldCheck", text: "Setări de bază", testid: "nav-base-settings" },
  ]},
];

function NavItem({ item, onClose, user }) {
  const locked = !can(user, ROUTE_FEATURE[item.to]);
  const Icon = ICONS[item.icon];
  return (
    <NavLink
      to={item.to} end={item.to === "/"} data-testid={item.testid}
      onClick={onClose}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-[9px] px-3 py-[10px] my-0.5 text-[13px] transition-colors ${
          isActive ? "bg-[#243755] text-white shadow-[inset_3px_0_var(--green)]" : "text-[#bdc8da] hover:bg-[#1c2c48] hover:text-white"
        }`
      }
    >
      <Icon size={17} />
      <span>{item.text}</span>
      {item.badge && <span className="ml-auto rounded bg-[#e78c2f] px-1.5 py-0.5 text-[9px] font-extrabold text-white">{item.badge}</span>}
      {isOff(user, ROUTE_FEATURE[item.to])
        ? <span className="ml-auto text-[9px] font-bold uppercase rounded px-1.5 py-0.5 bg-white/10" data-testid={`${item.testid}-disabled`}>Indisponibil</span>
        : locked && !item.badge && <Lock size={12} className="ml-auto opacity-70" data-testid={`${item.testid}-locked`} />}
    </NavLink>
  );
}

export function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expandedGroup, setExpandedGroup] = useState("");
  const initials = (user?.name || user?.email || "A").slice(0, 2).toUpperCase();
  const visibleItems = (items) => items.filter((it) => (!it.admin || (user?.role || "admin") === "admin")
    && (!it.platform || user?.platform)
    && (!it.owner || (!user?.plan?.exempt && user?.account_type !== "team")));

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={onClose} />}
      <aside
        data-testid="sidebar"
        className={`fixed md:sticky top-0 z-40 h-screen w-[260px] shrink-0 flex flex-col overflow-y-auto px-3.5 py-5 text-white transition-transform
          ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
        style={{ background: "linear-gradient(180deg, var(--navy), #0c1424)" }}
      >
        <div className="flex items-center gap-3 px-2 mb-4">
          <BrandMark size={38} />
          <div className="min-w-0 leading-tight">
            <div className="font-extrabold tracking-wide text-[16px]">DNS ENERGY</div>
            <div className="text-[9px] uppercase tracking-[1.4px]" style={{ color: "#aab8d1" }}>Documentație fotovoltaică</div>
          </div>
          <button aria-label="Închide meniul" className="ml-auto md:hidden" onClick={onClose}><X size={20} /></button>
        </div>

        <nav className="flex-1" aria-label="Navigare principală">
          {MAIN_NAV.map((item) => <NavItem key={item.to} item={item} onClose={onClose} user={user} />)}
          <div className="mt-4 border-t border-white/10 pt-2">
            {GROUPS.map((group) => {
              const items = visibleItems(group.items);
              if (!items.length) return null;
              const active = items.some((item) => location.pathname === item.to);
              const expanded = active || expandedGroup === group.label;
              return (
                <section key={group.label} className="py-0.5">
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setExpandedGroup(expanded && !active ? "" : group.label)}
                    className="flex w-full items-center justify-between rounded-[9px] px-3 py-2.5 text-left text-[11px] font-bold uppercase tracking-wide text-[#8f9db3] hover:bg-white/5 hover:text-white"
                  >
                    <span>{group.label}</span><ChevronDown size={14} className={expanded ? "rotate-180 transition-transform" : "transition-transform"} />
                  </button>
                  {expanded && <div className="pb-1">{items.map((item) => <NavItem key={item.to} item={item} onClose={onClose} user={user} />)}</div>}
                </section>
              );
            })}
          </div>
        </nav>

        <div className="mt-4 pt-4 border-t border-white/10">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="h-9 w-9 rounded-full grid place-items-center font-bold text-[13px]" style={{ background: "#e8f5ed", color: "#16834b" }}>{initials}</div>
            <div className="min-w-0">
              <div className="text-[12px] font-semibold truncate">{user?.name}</div>
              <div className="text-[10px] truncate" style={{ color: "#aab8d1" }}>{user?.email}</div>
              <div className="text-[10px] font-bold" style={{ color: "var(--cyan)" }} data-testid="sidebar-plan">Abonament: {user?.plan?.exempt ? "FULL (platformă)" : `${user?.plan?.name} · ${user?.plan?.status}`}</div>
            </div>
          </div>
          <button
            data-testid="logout-btn"
            onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center gap-2 w-full rounded-[9px] px-3 py-2.5 text-[12px] text-[#bdc8da] hover:bg-[#1c2c48] hover:text-white"
          >
            <LogOut size={16} /> Deconectare
          </button>
        </div>
      </aside>
    </>
  );
}
