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
import "@/App.css";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen grid place-items-center text-sm text-slate-400">Se încarcă...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/clienti" element={<ModulePage moduleKey="clients" />} />
        <Route path="/prosumator" element={<ModulePage moduleKey="prosumator" />} />
        <Route path="/diu" element={<ModulePage moduleKey="diu" />} />
        <Route path="/lucrari" element={<ModulePage moduleKey="works" />} />
        <Route path="/mono" element={<ModulePage moduleKey="mono" />} />
        <Route path="/tablouri" element={<ModulePage moduleKey="panels" />} />
        <Route path="/antiinsularizare" element={<ModulePage moduleKey="anti" />} />
        <Route path="/pram" element={<ModulePage moduleKey="pram" />} />
        <Route path="/echipamente" element={<ModulePage moduleKey="equipment" />} />
        <Route path="/spor-putere" element={<ModulePage moduleKey="power" />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/catalog-echipamente" element={<EquipmentCatalog />} />
        <Route path="/simulare" element={<Simulare />} />
        <Route path="/distribuitori" element={<Operators />} />
        <Route path="/documente" element={<Documents />} />
        <Route path="/setari" element={<Settings />} />
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
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}
