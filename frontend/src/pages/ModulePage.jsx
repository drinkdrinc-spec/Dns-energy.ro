import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api, API, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";
import { hasConfiguredStorage } from "@/lib/cefStorage";
import { MODULES } from "@/config/modules";
import { PageHeader, Btn } from "@/components/Layout";
import { Plus, Pencil, Trash2, Search, X } from "lucide-react";
import { toast } from "sonner";
import { GeneratedDocs } from "@/components/ProsumatorTools";
import { DossierDocumentStart } from "@/components/dossier/DossierDocumentStart";
import { ClientConversation } from "@/components/dossier/ClientConversation";
import { DossierActivity } from "@/components/dossier/DossierActivity";
import { CefEditor } from "@/components/cef/CefEditor";
import { DossierOpis } from "@/components/dossier/DossierOpis";
import { DossierExtras } from "@/components/dossier/DossierExtras";
import { ClientDocs } from "@/components/dossier/ClientDocs";
import { SignRequests } from "@/components/sign/SignRequests";
import { SldPanel } from "@/components/sld/SldPanel";

import { AssignBox } from "@/components/AssignBox";
import { useAuth } from "@/context/AuthContext";
import { PowerDossier, SimpleDossierBtn } from "@/components/dossier/PowerDossier";
import { AtrDossier } from "@/components/dossier/AtrDossier";
import { PifPanel } from "@/components/dossier/PifPanel";
import { AiDossierCheck } from "@/components/ai/AiDossierCheck";
import { AiRacordCheck } from "@/components/ai/AiRacordCheck";
import { AiOdReview } from "@/components/ai/AiOdReview";
import { AiDraft } from "@/components/ai/AiDraft";
import { DiuDossier } from "@/components/dossier/DiuDossier";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { can } from "@/lib/plan";
import { ProsumatorQuickForm } from "@/components/dossier/ProsumatorQuickForm";
import { AtrQuickForm } from "@/components/dossier/AtrQuickForm";
import { DiuQuickForm } from "@/components/dossier/DiuQuickForm";

function installedPanelKwp(pros) {
  if (!pros) return "";
  const number = (value) => {
    const parsed = Number(String(value ?? "").replace(",", "."));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const inverters = pros.cef?.inverters || [];
  const calculated = inverters.reduce((total, inverter) => {
    const panelW = number(inverter.panel_w);
    const panels = (inverter.strings || []).reduce((sum, string) => sum + number(string.panels), 0);
    const count = Math.max(1, number(inverter.count || inverter.quantity) || 1);
    return total + panels * panelW * count / 1000;
  }, 0);
  if (calculated > 0) return Number(calculated.toFixed(3));
  const legacyPanels = number(pros.panel_count);
  const legacyW = number(pros.panel_w);
  if (legacyPanels > 0 && legacyW > 0) return Number((legacyPanels * legacyW / 1000).toFixed(3));
  return pros.cef?.total_kwp || pros.panel_kwp || pros._kwp || "";
}

const PROSUMER_OD_STAGES = [
  "Depunerea cererii de racordare",
  "Emiterea avizului tehnic de racordare",
  "Încheierea contractului de racordare și încredințarea execuției lucrării de racordare",
  "Execuția instalației de racordare",
  "Depunerea dosarului instalației electrice interioare",
  "Recepția instalației electrice de racordare",
  "Emiterea certificatului de racordare",
  "Încheierea contractului de furnizare a energiei electrice",
  "Punerea sub tensiune a instalației de utilizare"
];

const PROSUMER_OD_STAGE_GUIDANCE = [
  ["Cererea de racordare", "Actele clientului și ale locului de consum", "Cererea ATR și anexa oficială potrivită operatorului și situației"],
  ["Emiterea avizului", "Avizul tehnic de racordare și condițiile impuse", "Notificările operatorului privind completări sau corecturi"],
  ["Contractul de racordare", "Contractul și documentele de execuție, dacă sunt cerute", "Dovada achitării tarifelor aplicabile"],
  ["Execuția racordării", "Proiectul și documentele lucrării de racordare", "Procesele-verbale și confirmările aferente execuției"],
  ["Dosarul instalației interioare", "DI-U, schema monofilară și documentele echipamentelor", "PRAM, verificări și procese-verbale PIF, după caz"],
  ["Recepția instalației", "Documentele de recepție și rezultatele probelor", "Remedierea și retrimiterea documentelor cerute de operator"],
  ["Certificatul de racordare", "Certificatul emis de operator și condițiile de exploatare", "Verifică puterile și datele tehnice față de dosarul depus"],
  ["Contractul de furnizare", "Contractul cu furnizorul ales", "Confirmarea datelor locului de consum și a titularului"],
  ["Punerea sub tensiune", "Notificarea operatorului și confirmarea stării finale", "Păstrează dovada comunicării și actualizează dosarul ca activ"],
];

const ATR_BOARD_STATUSES = ["În lucru", "Generată", "Depusă", "Completări cerute", "ATR emis"];

