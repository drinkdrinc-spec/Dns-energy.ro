"""Validation helpers for documents referenced by a prosumer dossier."""


def verify_dossier_attachments(info: dict, get_object, legacy_unavailable: type) -> dict:
    """Read referenced files once so stale storage pointers cannot count as attached evidence."""
    checked = {}
    for position in info.get("positions", []):
        refs = list(position.get("files") or [])
        if position.get("upload"):
            refs.append(position["upload"])
        unavailable = []
        for ref in refs:
            path = str((ref or {}).get("storage_path") or "").strip()
            if not path:
                continue
            if path not in checked:
                try:
                    data, _ = get_object(path)
                    checked[path] = None if data else "Fișierul stocat este gol. Reîncarcă documentul."
                except legacy_unavailable:
                    checked[path] = "Documentul istoric nu mai poate fi citit. Reîncarcă documentul în dosar sau în catalog."
                except FileNotFoundError:
                    checked[path] = "Fișierul nu a putut fi găsit în spațiul de stocare. Reîncarcă documentul."
                except Exception:
                    # A transient storage/network error must not be shown as a valid attachment.
                    checked[path] = "Fișierul nu a putut fi verificat acum. Reîncarcă-l sau verifică din nou dosarul."
            issue = checked[path]
            if issue:
                name = str((ref or {}).get("original_filename") or "Document atașat")
                unavailable.append(f"{name}: {issue}")
        if unavailable:
            position["unavailable_files"] = list(dict.fromkeys(unavailable))
            position["missing"] = list(dict.fromkeys([*(position.get("missing") or []), *unavailable]))
            position["auto_status"] = "de completat"
            position["status"] = "de completat"
    info["missing_total"] = sum(len(p.get("missing") or []) for p in info.get("positions", [])) + len(info.get("common_missing") or [])
    info["complete"] = info["missing_total"] == 0
    return info
