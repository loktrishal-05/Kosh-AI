import { notFound } from "next/navigation";
import { clients } from "../../../lib/mock";
import { ClientDetail } from "../../../components/ClientDetail";

export function generateStaticParams() { return clients.map(({ id }) => ({ id })); }
export default async function ClientPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const client = clients.find(client => client.id === id);
  if (!client) notFound();
  return <ClientDetail client={client} />;
}
