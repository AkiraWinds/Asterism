// frontend/src/app/graph/page.tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import { ConceptGraphView } from "@/components/ConceptGraphView";
import { ReviewQueuePanel } from "@/components/ReviewQueuePanel";

export default function GraphPage() {
  // Bumped after a review-queue resolution so ConceptGraphView remounts and
  // refetches — a merge changes node/edge counts the force graph otherwise
  // wouldn't know to reload.
  const [graphVersion, setGraphVersion] = useState(0);

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
        <ReviewQueuePanel onResolved={() => setGraphVersion((v) => v + 1)} />
      </div>
      <div className="mt-6">
        <ConceptGraphView key={graphVersion} />
      </div>
    </main>
  );
}
