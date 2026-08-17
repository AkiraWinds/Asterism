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
      <Link href="/" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 font-heading text-3xl font-bold tracking-tight text-foreground">Concept Graph</h1>
      <div className="mt-6">
        <ReviewQueuePanel onResolved={() => setGraphVersion((v) => v + 1)} />
      </div>
      <div className="mt-6">
        <ConceptGraphView key={graphVersion} />
      </div>
    </main>
  );
}
