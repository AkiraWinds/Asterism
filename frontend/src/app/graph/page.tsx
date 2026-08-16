// frontend/src/app/graph/page.tsx
import Link from "next/link";
import { ConceptGraphView } from "@/components/ConceptGraphView";

export default function GraphPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Link href="/" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 font-heading text-3xl font-bold tracking-tight text-foreground">Concept Graph</h1>
      <div className="mt-6">
        <ConceptGraphView />
      </div>
    </main>
  );
}
