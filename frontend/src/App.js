import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ModulePage from "@/pages/ModulePage";
import Documents from "@/pages/Documents";
import Catalog from "@/pages/Catalog";
import Operators from "@/pages/Operators";
import Simulare from "@/pages/Simulare";
import Settings from "@/pages/Settings";
import EquipmentCatalog from "@/pages/EquipmentCatalog";
import BaseSettings from "@/pages/BaseSettings";
import SignPage from "@/pages/SignPage";
import RemoteSigning from "@/pages/RemoteSigning";
import Users from "@/pages/Users";
import Subscription from "@/pages/Subscription";
import AdminBilling from "@/pages/AdminBilling";
import FormsRegistry from "@/pages/FormsRegistry";
import PlatformModules from "@/pages/PlatformModules";
import AiAssistant from "@/pages/AiAssistant";
import Offers from "@/pages/Offers";
import Contracts from "@/pages/Contracts";
import OperatorAttest from "@/pages/OperatorAttest";
import AdminOperators from "@/pages/AdminOperators";
import AnreDossiers from "@/pages/AnreDossiers";
import SchemaTehnica from "@/pages/SchemaTehnica";
import DistributionPortals from "@/pages/DistributionPortals";
import ArchivedDossiers from "@/pages/ArchivedDossiers";
import { Gate } from "@/components/UpgradeGate";
import { ROUTE_FEATURE } from "@/lib/plan";
import "@/App.css";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen grid place-items-center text-sm text-slate-400">Se încarcă...</div>;
  if (!user) { if (window.location.search) sessionStorage.setItem("den_next", window.location.pathname + window.location.search); return <Navigate to="/login" replace />; }
  return children;
}

function AfterLogin() {
  // Read without side effects during render (StrictMode renders twice); clear after mount
  const [next] = useState(() => sessionStorage.getItem("den_next"));
  useEffect(() => { sessionStorage.removeItem("den_next"); }, []);
  return <Navigate to={next || "/"} replace />;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <AfterLogin /> : <Login />} />
      <Route path="/semneaza/:token" element={<SignPage />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/semnare" element={<Gate feat={ROUTE_FEATURE["/semnare"]}><RemoteSigning /></Gate>} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/clienti" element={<Gate feat={ROUTE_FEATURE["/clienti"]}><ModulePage moduleKey="clients" /></Gate>} />
        <Route path="/prosumator" element={<Gate feat={ROUTE_FEATURE["/prosumator"]}><ModulePage moduleKey="prosumator" /></Gate>} />
        <Route path="/diu" element={<Gate feat={ROUTE_FEATURE["/diu"]}><ModulePage moduleKey="diu" /></Gate>} />
        <Route path="/lucrari" element={<Gate feat={ROUTE_FEATURE["/lucrari"]}><ModulePage moduleKey="works" /></Gate>} />
        <Route path="/mono" element={<Gate feat={ROUTE_FEATURE["/mono"]}><ModulePage moduleKey="mono" /></Gate>} />
        <Route path="/tablouri" element={<Gate feat={ROUTE_FEATURE["/tablouri"]}><ModulePage moduleKey="panels" /></Gate>} />
        <Route path="/antiinsularizare" element={<Gate feat={ROUTE_FEATURE["/antiinsularizare"]}><ModulePage moduleKey="anti" /></Gate>} />
        <Route path="/pram" element={<Gate feat={ROUTE_FEATURE["/pram"]}><ModulePage moduleKey="pram" /></Gate>} />
        <Route path="/echipamente" element={<Gate feat={ROUTE_FEATURE["/echipamente"]}><ModulePage moduleKey="equipment" /></Gate>} />
        <Route path="/spor-putere" element={<Gate feat={ROUTE_FEATURE["/spor-putere"]}><ModulePage moduleKey="power" /></Gate>} />
        <Route path="/cerere-atr" element={<Gate feat="atr"><ModulePage moduleKey="atr" /></Gate>} />
        <Route path="/formulare-oficiale" element={<FormsRegistry />} />
        <Route path="/portaluri-distribuitori" element={<DistributionPortals />} />
        <Route path="/catalog" element={<Gate feat={ROUTE_FEATURE["/catalog"]}><Catalog /></Gate>} />
        <Route path="/catalog-echipamente" element={<Gate feat={ROUTE_FEATURE["/catalog-echipamente"]}><EquipmentCatalog /></Gate>} />
        <Route path="/setari-baza" element={<Gate feat={ROUTE_FEATURE["/setari-baza"]}><BaseSettings /></Gate>} />
        <Route path="/simulare" element={<Gate feat={ROUTE_FEATURE["/simulare"]}><Simulare /></Gate>} />
        <Route path="/distribuitori" element={<Gate feat={ROUTE_FEATURE["/distribuitori"]}><Operators /></Gate>} />
        <Route path="/documente" element={<Gate feat={ROUTE_FEATURE["/documente"]}><Documents /></Gate>} />
        <Route path="/dosare-arhivate" element={<Gate feat="prosumator"><ArchivedDossiers /></Gate>} />
        <Route path="/setari" element={<Settings />} />
        <Route path="/utilizatori" element={<Users />} />
        <Route path="/abonament" element={<Subscription />} />
        <Route path="/abonamente-admin" element={<AdminBilling />} />
        <Route path="/module-platforma" element={<PlatformModules />} />
        <Route path="/asistent-ai" element={<Gate feat="ai_gpt"><AiAssistant /></Gate>} />
        <Route path="/oferte" element={<Gate feat="oferte"><Offers /></Gate>} />
        <Route path="/atestat-anre" element={<OperatorAttest />} />
        <Route path="/dosare-anre" element={<AnreDossiers />} />
        <Route path="/schema-tehnica" element={<SchemaTehnica />} />
        <Route path="/operatori-anre" element={<AdminOperators />} />
        <Route path="/contracte" element={<Gate feat="oferte"><Contracts /></Gate>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}
