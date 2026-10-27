# D-ENERGY — PRD

## Problem statement
Web app "D-ENERGY" for DNS HOSTESS S.R.L. (Romanian UI, responsive) to manage electrical & PV works and generate prosumer dossiers. JWT auth, MongoDB, Emergent Object Storage. Prosumer dossier and DI-U are separate modules. Model for dossier structure/wording: PUBLISERV PDF (text extracted at /app/memory/model/text.txt, original at /app/memory/model/publiserv.pdf). Never use PUBLISERV data as defaults; never invent measurements, numbers, signatures, stamps, authorizations.

## Architecture
- backend/server.py: auth, generic CRUD /api/data/{module} (+audit, guard for staff/instruments), AI extract, import, CEF check, catalog, dossier endpoints (/api/dossier/{id}, /item/{key}, /file/{key}?fmt=pdf|docx, /export, /finalize, /reopen), /api/audit, effective_settings (signers/instrument eligibility).
- backend/docgen.py: block-based documents (PDF reportlab + DOCX python-docx), Ctx (client sheet has priority for client fields, then dossier, then settings). Docs reproduce PUBLISERV model: Anexa 2 Notificare, Împuternicire, Declarație AFM, Declarația executantului, Declarație conformitate HGR 1022, PV recepție + Anexă serii, PV PIF finală, PV teste OD + Teste și Verificări, Buletin priză, Buletin reglaj, Declarație autenticitate (opis), schema (schema_cef.py, landscape, protection table + cartuș).
- backend/opis.py: positions 1-10 generated, 11-13 client docs (client.docs slots), 14-17 catalog datasheet/conformity (inverter, panel), 18+ battery/smart meter; statuses de completat/generat/necesită semnătură/atașat; missing report (common_missing + per position); export bundle (opis first, CIORNĂ watermark if incomplete).
- frontend: ModulePage (config-driven, section fields), components/dossier (DossierOpis, DossierExtras signers/reglaj/tests, ClientDocs), components/cef/*, pages/BaseSettings.jsx (Firmă & ANRE, Aparate de măsură, Personal with authorizations + verified flag, Jurnal), EquipmentCatalog.

## Implemented (dates)
- 2026-06 MVP modules. 2026-10: AI PDF import (Gemini 3 Flash), 11 docs, CEF multi-inverter editor + checks + schema, DB catalog.
- 2026-10-27: PUBLISERV-model dossier (opis, statuses, upload/preview, PDF+Word, full export, missing report), full client sheet, base settings (company/ANRE/stamp/armătură uploads, instruments, staff authorizations, signers per role with eligibility blocking, finalize snapshot freezing settings, audit log). Tests iteration_4 (50 passed) + iteration_5 test-suite fix.

## Backlog
- P0: Remote signing module "Semnare la distanță" (approved spec: simple electronic signature with evidence; single-use link valid until signed + configurable expiry (default 7 days), revocable, resend/new link keeping history; statuses De trimis/Link trimis/Deschis/Semnat/Refuzat/Expirat; mobile full-document view; explicit intent, declared identity, UTC time, IP, UA, SHA-256 before/after; email OTP via Emergent-managed Resend (user accepted recommended); final PDF with evidence page auto-attached to opis position (replaces generated in export). Must be labelled "semnătură electronică simplă" — NOT qualified. QES providers (Simplifi/certSIGN/Yousign) only later with user's keys.
- P1: Official per-operator templates (Delgaz, Rețele Electrice, Oltenia); optional insertion of authorized stamp/signature images on user action; RO date picker.
- P2: Multi-user roles UI; DI-U from prosumer dossier.
