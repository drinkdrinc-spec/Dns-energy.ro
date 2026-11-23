"""Submission evidence checks for generated DI-U packages."""

from datetime import datetime, timezone


def supporting_status(record: dict, settings: dict, instrument: dict | None = None) -> dict:
    """Check real company and measuring-device evidence needed alongside DI-U forms."""
    today = datetime.now(timezone.utc).date().isoformat()
    available, missing = [], []

    anre = settings.get("anre_file") or {}
    if anre.get("storage_path"):
        expiry = str(settings.get("anre_valid") or "")
        if not expiry:
            missing.append("Valabilitatea atestatului ANRE al firmei nu este completată în Setări → Firmă.")
        elif expiry < today:
            missing.append("Atestatul ANRE al firmei este expirat — încarcă atestatul valabil în Setări → Firmă.")
        else:
            available.append("Atestat ANRE firmă")
    else:
        missing.append("Atestatul ANRE al firmei lipsește — încarcă-l în Setări → Firmă.")

    if not settings.get("_stamp_path"):
        missing.append("Ștampila firmei lipsește — încarc-o în Setări → Firmă.")

    pm = record.get("pram_m") or {}
    measured = any(pm.get(key) not in (None, "") for key in ("earth_ohm", "test_v")) or any(
        circuit.get(key) not in (None, "")
        for circuit in record.get("circuits") or [] if isinstance(circuit, dict)
        for key in ("r_pe", "riso", "rcd_i", "rcd_t")
    )
    if measured and record.get("pram_source") not in ("third_party", "none"):
        if not instrument:
            missing.append("Aparatul PRAM nu este selectat — alege-l din Setări → Aparate de măsură.")
        else:
            expiry = str(instrument.get("expires") or "")
            cert = instrument.get("file") or {}
            label = "Certificatul metrologic al aparatului PRAM"
            if not cert.get("storage_path"):
                missing.append(f"{label} lipsește — încarcă-l în Setări → Aparate de măsură.")
            elif not expiry:
                missing.append(f"Valabilitatea pentru {label.lower()} nu este completată în Setări.")
            elif expiry < today:
                missing.append(f"{label} este expirat — încarcă certificatul valabil.")
            else:
                available.append(f"{label} — {instrument.get('maker_model') or instrument.get('name') or 'aparat'}")
    return {"available": available, "missing": missing}


def collect_signed_sources(keys, signed, titles, get_object, max_total, used=0, limit_label="100 MB"):
    """Read exact signed source PDFs so they can accompany a compiled copy."""
    files, issues = [], []
    for key in keys:
        source = signed.get(key) or {}
        path = source.get("storage_path")
        if not path:
            continue
        label = titles.get(key, key)
        try:
            data, _content_type = get_object(path)
            if used + len(data) > max_total:
                issues.append(f"Document semnat — {label} a fost omis, limita de {limit_label} a pachetului a fost atinsă.")
                continue
            used += len(data)
            files.append({"key": key, "title": label, "filename": f"Documente semnate/{key}.pdf", "data": data})
        except Exception:
            issues.append(f"Document semnat — {label} nu a putut fi citit din arhivă.")
    return {"files": files, "issues": issues, "used": used}
