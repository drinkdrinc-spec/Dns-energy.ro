import { NavLink, useNavigate } from "react-router-dom";
import { BrandMark } from "@/components/BrandMark";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert, Archive,
  FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, LogOut, X, Briefcase, ShieldCheck, PenLine, Lock, CreditCard, Receipt, Sparkles,
} from "lucide-react";
import { can, isOff, ROUTE_FEATURE } from "@/lib/plan";

const ICONS = { LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert, FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, Briefcase, ShieldCheck, PenLine, CreditCard, Receipt, Sparkles, Archive };

const NAV = [
  { label: "Flux dosare", items: [
    { to: "/clienti", icon: "Users", text: "Clienți și documente", testid: "nav-clients" },
    { to: "/prosumator", icon: "SunMedium", text: "Dosar prosumator", testid: "nav-prosumator" },
    { to: "/cerere-atr", icon: "FileCheck2", text: "Cerere ATR", testid: "nav-atr" },
    { to: "/spor-putere", icon: "PlugZap", text: "Spor de putere", testid: "nav-power" },
    { to: "/diu", icon: "FolderOpen", text: "Dosar DIU", testid: "nav-diu" },
    { to: "/dosare-anre", icon: "Briefcase", text: "Dosare ANRE", testid: "nav-anre" },
    { to: "/catalog-echipamente", icon: "Cpu", text: "Catalog echipamente", testid: "nav-equipment-catalog" },
    { to: "/mono", icon: "GitBranch", text: "Schema monofilară", testid: "nav-mono" },
    { to: "/pram", icon: "FileCheck2", text: "Buletine PRAM", testid: "nav-pram" },
  ]},
  { label: "Principal", items: [
    { to: "/", icon: "LayoutDashboard", text: "Panou principal", testid: "nav-home" },
    { to: "/asistent-ai", icon: "Sparkles", text: "Asistent AI", testid: "nav-ai-assistant" },
    { to: "/oferte", icon: "Receipt", text: "Oferte de preț", testid: "nav-offers" },
    { to: "/contracte", icon: "FileCheck2", text: "Contracte", testid: "nav-contracts" },
  ]},
  { label: "Tehnic", items: [
    { to: "/lucrari", icon: "Briefcase", text: "Gestionarea lucrărilor", testid: "nav-works" },
    { to: "/tablouri", icon: "LayoutGrid", text: "Tablouri electrice", testid: "nav-panels" },
    { to: "/antiinsularizare", icon: "ShieldAlert", text: "Antiinsularizare", testid: "nav-anti" },
    { to: "/echipamente", icon: "Cpu", text: "Echipamente", testid: "nav-equipment" },
    { to: "/semnare", icon: "PenLine", text: "Semnare la distanță", testid: "nav-remote-signing" },
    { to: "/setari-baza", icon: "ShieldCheck", text: "Setări de bază", testid: "nav-base-settings" },
    { to: "/catalog", icon: "BookOpen", text: "Catalog tehnic (linkuri)", testid: "nav-catalog" },
  ]},
  { label: "Racordare și resurse", items: [
    { to: "/formulare-oficiale", icon: "BookOpen", text: "Registru formulare oficiale", testid: "nav-forms" },
    { to: "/simulare", icon: "SunMedium", text: "Simulare proiect & hartă", testid: "nav-project" },
    { to: "/distribuitori", icon: "Network", text: "Distribuitori România", testid: "nav-operators" },
    { to: "/portaluri-distribuitori", icon: "Network", text: "Portal depunere după POD", testid: "nav-distribution-portals" },
  ]},
  { label: "Administrare", items: [
    { to: "/documente", icon: "Files", text: "Documente", testid: "nav-documents" },
    { to: "/dosare-arhivate", icon: "Archive", text: "Dosare vechi / delegare", testid: "nav-archived-dossiers" },
    { to: "/setari", icon: "Settings", text: "Setări", testid: "nav-settings" },
    { to: "/utilizatori", icon: "ShieldCheck", text: "Utilizatori și roluri", testid: "nav-users", admin: true },
    { to: "/abonament", icon: "CreditCard", text: "Abonament și facturare", testid: "nav-subscription", owner: true },
    { to: "/atestat-anre", icon: "ShieldCheck", text: "Atestat ANRE firmă", testid: "nav-operator-attest", owner: true },
    { to: "/dosare-anre", icon: "Briefcase", text: "Dosare ANRE (premium)", testid: "nav-anre" },
    { to: "/abonamente-admin", icon: "Receipt", text: "Utilizatori și abonamente", testid: "nav-admin-billing", platform: true },
    { to: "/module-platforma", icon: "LayoutGrid", text: "Module platformă", testid: "nav-platform-modules", platform: true },
    { to: "/operatori-anre", icon: "ShieldCheck", text: "Operatori și atestate ANRE", testid: "nav-admin-operators", platform: true },
  ]},
];

export function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.name || user?.email || "A").slice(0, 2).toUpperCase();

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={onClose} />}
      <aside
        data-testid="sidebar"
        className={`fixed md:sticky top-0 z-40 h-screen w-[260px] shrink-0 flex flex-col overflow-y-auto px-3.5 py-6 text-white transition-transform
          ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
        style={{ background: "linear-gradient(180deg, var(--navy), #0c1424)" }}
      >
        <div className="flex items-center gap-3 px-2 mb-4">
          <BrandMark size={42} />
          <div className="leading-tight">
            <div className="font-extrabold tracking-wide text-[17px]">D-ENERGY</div>
            <div className="text-[10px]" style={{ color: "#aab8d1" }}>DNS HOSTESS S.R.L.</div>
          </div>
          <button className="ml-auto md:hidden" onClick={onClose}><X size={20} /></button>
        </div>

        <nav className="flex-1">
          {NAV.map((grp) => (
            <div key={grp.label}>
              <div className="font-bold uppercase" style={{ color: "#7f91ae", fontSize: 10, letterSpacing: 1.5, padding: "20px 12px 8px" }}>{grp.label}</div>
              {grp.items.filter((it) => (!it.admin || (user?.role || "admin") === "admin") && (!it.platform || user?.platform)
                && (!it.owner || (!user?.plan?.exempt && user?.account_type !== "team"))).map((it) => {
                const locked = !can(user, ROUTE_FEATURE[it.to]);
                const Icon = ICONS[it.icon];
                return (
                  <NavLink
                    key={it.to} to={it.to} end={it.to === "/"} data-testid={it.testid}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-[10px] px-3 py-3 my-0.5 text-[13px] transition-colors ${
                        isActive ? "bg-[#243755] text-white shadow-[inset_3px_0_var(--cyan)]" : "text-[#bdc8da] hover:bg-[#1c2c48] hover:text-white"
                      }`
                    }
                  >
                    <Icon size={17} />
                    <span>{it.text}</span>
                    {isOff(user, ROUTE_FEATURE[it.to])
                      ? <span className="ml-auto text-[9px] font-bold uppercase rounded px-1.5 py-0.5 bg-white/10" data-testid={`${it.testid}-disabled`}>Indisponibil</span>
                      : locked && <Lock size={12} className="ml-auto opacity-70" data-testid={`${it.testid}-locked`} />}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="mt-6 pt-4 border-t border-white/10">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="h-9 w-9 rounded-full grid place-items-center font-bold text-[13px]" style={{ background: "#e6f1ff", color: "#2469c8" }}>{initials}</div>
            <div className="min-w-0">
              <div className="text-[12px] font-semibold truncate">{user?.name}</div>
              <div className="text-[10px] truncate" style={{ color: "#8191aa" }}>{user?.email}</div>
              <div className="text-[10px] font-bold" style={{ color: "var(--cyan)" }} data-testid="sidebar-plan">Abonament: {user?.plan?.exempt ? "FULL (platformă)" : `${user?.plan?.name} · ${user?.plan?.status}`}</div>
            </div>
          </div>
          <button
            data-testid="logout-btn"
            onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center gap-2 w-full rounded-[10px] px-3 py-2.5 text-[12px] text-[#bdc8da] hover:bg-[#1c2c48] hover:text-white"
          >
            <LogOut size={16} /> Deconectare
          </button>
        </div>
      </aside>
    </>
  );
}
