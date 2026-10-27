import { NavLink, useNavigate } from "react-router-dom";
import { BrandMark } from "@/components/BrandMark";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert,
  FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, LogOut, X, Briefcase,
} from "lucide-react";

const ICONS = { LayoutDashboard, Users, FolderOpen, GitBranch, LayoutGrid, ShieldAlert, FileCheck2, Cpu, BookOpen, PlugZap, SunMedium, Network, Files, Settings, Briefcase };

const NAV = [
  { label: "Principal", items: [
    { to: "/", icon: "LayoutDashboard", text: "Panou principal", testid: "nav-home" },
    { to: "/clienti", icon: "Users", text: "Clienți", testid: "nav-clients" },
  ]},
  { label: "Dosare", items: [
    { to: "/prosumator", icon: "SunMedium", text: "Dosar de prosumator", testid: "nav-prosumator" },
    { to: "/diu", icon: "FolderOpen", text: "Dosar de utilizare (DI-U)", testid: "nav-diu" },
    { to: "/lucrari", icon: "Briefcase", text: "Gestionarea lucrărilor", testid: "nav-works" },
  ]},
  { label: "Tehnic", items: [
    { to: "/mono", icon: "GitBranch", text: "Scheme monofilare", testid: "nav-mono" },
    { to: "/tablouri", icon: "LayoutGrid", text: "Tablouri electrice", testid: "nav-panels" },
    { to: "/antiinsularizare", icon: "ShieldAlert", text: "Antiinsularizare", testid: "nav-anti" },
    { to: "/pram", icon: "FileCheck2", text: "Buletine PRAM", testid: "nav-pram" },
    { to: "/echipamente", icon: "Cpu", text: "Echipamente", testid: "nav-equipment" },
    { to: "/catalog-echipamente", icon: "Cpu", text: "Catalog echipamente", testid: "nav-equipment-catalog" },
    { to: "/catalog", icon: "BookOpen", text: "Catalog tehnic (linkuri)", testid: "nav-catalog" },
  ]},
  { label: "Racordare", items: [
    { to: "/spor-putere", icon: "PlugZap", text: "Spor de putere / BMP", testid: "nav-power" },
    { to: "/simulare", icon: "SunMedium", text: "Simulare proiect & hartă", testid: "nav-project" },
    { to: "/distribuitori", icon: "Network", text: "Distribuitori România", testid: "nav-operators" },
  ]},
  { label: "Administrare", items: [
    { to: "/documente", icon: "Files", text: "Documente", testid: "nav-documents" },
    { to: "/setari", icon: "Settings", text: "Setări", testid: "nav-settings" },
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
              {grp.items.map((it) => {
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
