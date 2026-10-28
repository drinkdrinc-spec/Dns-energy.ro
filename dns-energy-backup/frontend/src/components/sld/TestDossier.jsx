import { useState } from "react";
import { toast } from "sonner";
import { FlaskConical, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";

export function TestDossierButtons({ onDone }) {
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/test-dossier");
      toast.success(`Dosar de test creat: ${data.number}` + (data.test_email ? ` · e-mailurile merg la ${data.test_email}` : " · fără e-mail de test — e-mailurile NU se trimit"));
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
    setBusy(false);
  };
  const remove = async () => {
    if (!window.confirm("Ștergi toate datele marcate TEST (dosare, clienți, personal, aparate, catalog, semnături de test)?")) return;
    const { data } = await api.delete("/test-dossier");
    toast.success(`${data.deleted} înregistrări de test șterse`); onDone();
  };
  return (
    <>
      <Btn variant="secondary" onClick={create} disabled={busy} data-testid="test-dossier-create"><FlaskConical size={15} /> Creează dosar de test</Btn>
      <Btn variant="secondary" onClick={remove} data-testid="test-dossier-delete"><Trash2 size={15} /> Șterge datele de test</Btn>
    </>
  );
}
