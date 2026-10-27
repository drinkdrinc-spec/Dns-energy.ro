import { PageHeader } from "@/components/Layout";
import { SignRequests } from "@/components/sign/SignRequests";

export default function RemoteSigning() {
  return (
    <div>
      <PageHeader eyebrow="Modul" title="Semnare la distanță" sub="Toate cererile de semnare. Cererile noi se creează din dosarul de prosumator (secțiunea Semnături)." />
      <SignRequests />
    </div>
  );
}
