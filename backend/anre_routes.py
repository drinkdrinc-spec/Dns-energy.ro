def items(d):
    out = []
    for it in AD.opis_items(d.get("kind")):
        st = (d.get("docs") or {}).get(it["key"]) or {}
        status = st.get("status") or ("generat — de verificat" if it["key"] in GEN else "lipsă")
        if it["key"] in GEN and st.get("approved"):
            status = "verificat"
        if it["key"] == "cert_constatator" and st.get("issued"):
            try:
                if (date.today() - date.fromisoformat(st["issued"])).days > 30:
                    status = "expirat / nevalid"
            except ValueError:
                status = "necesită verificare manuală"
        out.append({**it, "source_label": SRC[it["source"]], "status": status, "file": st.get("name"), "issued": st.get("issued"), "notes": st.get("notes")})
    return out


# Minimum electrician qualifications by attestation type, transcribed from
# Annex 8 of ANRE Order 134/2021. Each entry is the required count per grade.
ANRE_MIN_STAFF = {
    "A": {"IIIB": 1, "IVB": 1},
    "A1": {"IIB": 2}, "A2": {"IIB": 1, "IIIB": 1}, "A3": {"IIB": 1, "IIIB": 1},
    "B": {"IIA": 1, "IIB": 1}, "Be": {"IIB": 2}, "Bi": {"IIB": 2}, "Bp": {"IIA": 2},
    "C1A": {"IIIA": 2}, "C1B": {"IVA": 2}, "C2A": {"IIIB": 2}, "C2B": {"IVB": 2},
    "D1": {"IVA": 2}, "D2": {"IVB": 2}, "E1": {"IVA": 2}, "E2": {"IVB": 2},
    "E2PA": {"IIIB": 1, "IVB": 1},
}


def staff_grades(value):
    normalized = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii").upper()
    normalized = re.sub(r"[^A-Z0-9]", "", normalized)
    return set(re.findall(r"IV[AB]|III[AB]|II[AB]", normalized))


def staff_name_key(value):
    normalized = unicodedata.normalize("NFD", str(value or ""))
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(normalized.casefold().split())


def check(d):
    its = items(d)
    c = d.get("company") or {}
    rep = {"at": now(), "present": [], "missing": [], "review": [], "incomplete": [], "issues": [], "actions": []}
    for i in its:
        (rep["present"] if i["status"] == "verificat" else rep["missing"] if i["status"] == "lipsă" else rep["review"]).append(f"{i['nr']}. {i['title']} — {i['status']}")
    for k, l in (("name", "denumire"), ("cui", "CUI"), ("regcom", "Nr. Reg. Comerțului"), ("address", "sediu social"), ("rep_name", "reprezentant legal"), ("email", "e-mail"), ("phone", "telefon")):
        if not c.get(k):
            rep["incomplete"].append(f"Date firmă: lipsește {l}")
    if d.get("kind") in ("nou", "b_c1a", "b_c2a", "vizare"):
        if not [x for x in d.get("equipment") or [] if x.get("name")]:
            rep["incomplete"].append("Lista dotărilor tehnico-materiale este goală (minimul din Anexa nr. 6)")
        raw_target_types = d.get("target_types") or []
        if isinstance(raw_target_types, str):
            raw_target_types = [raw_target_types]
        target_types = list(dict.fromkeys(str(x).strip() for x in raw_target_types if str(x).strip()))
        if not target_types:
            rep["incomplete"].append("Tipul de atestat solicitat nu este ales")
        complete_org = [
            row for row in d.get("org") or []
            if all(str(row.get(field) or "").strip() for field in ("dept", "name", "activity"))
        ]
        if not complete_org:
            rep["incomplete"].append("Organigrama lipsește sau nu are un compartiment, responsabil și activitate completate")
        named_staff = {}
        for person in d.get("staff") or []:
            key = staff_name_key(person.get("name"))
            if key:
                named_staff.setdefault(key, person)
        for target in target_types:
            requirements = ANRE_MIN_STAFF.get(target)
            if not requirements:
                rep["issues"].append(f"Tipul de atestat {target} nu are o regulă de personal mapată; verificați Anexa nr. 8 înainte de finalizare")
                continue
            for grade, required_count in requirements.items():
                found = sum(1 for person in named_staff.values() if grade in staff_grades(person.get("grade")))
                if found < required_count:
                    rep["incomplete"].append(
                        f"Personal insuficient pentru {target}: lipsesc {required_count - found} electrician(i) cu autorizare {grade} conform Anexei nr. 8"
                    )
        for person in named_staff.values():
            if person.get("grade") and not person.get("license"):
                rep["incomplete"].append(f"Fișa de personal: lipsește numărul legitimației ANRE pentru {person.get('name')}")
    if d.get("kind") in ("b_c1a", "b_c2a") and not has_attestation_type(c.get("attest_types"), "B"):
        rep["issues"].append("Solicitare de extindere de la B, dar atestatul existent declarat nu conține tipul B — verificați eligibilitatea")
    for s in d.get("staff") or []: