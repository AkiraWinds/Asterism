// frontend/src/app/graph/page.tsx
import Link from "next/link";
import { ConceptGraphView } from "@/components/ConceptGraphView";

export default function GraphPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Link
        href="/"
        className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
      >
        ← Back
      </Link>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
        Concept Graph
      </h1>
      <div className="mt-6">
        <ConceptGraphView />
      </div>
    </main>
  );
}
