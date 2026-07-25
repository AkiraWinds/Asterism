import { getSource } from "@/lib/api";

export default async function SourcePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const source = await getSource(id);

  return (
    <main style={{ padding: 24 }}>
      <h1>{source.title}</h1>
      <pre style={{ whiteSpace: "pre-wrap" }}>{source.content}</pre>
    </main>
  );
}
