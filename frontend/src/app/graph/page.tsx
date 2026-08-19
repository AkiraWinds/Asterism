// frontend/src/app/graph/page.tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import { ConceptGraphView } from "@/components/ConceptGraphView";
import { ReviewQueuePanel } from "@/components/ReviewQueuePanel";
import { WikiPagePanel } from "@/components/WikiPagePanel";
import { GraphData } from "@/lib/api";

export default function GraphPage() {
  // Bumped after a review-queue resolution so ConceptGraphView remounts and
  // refetches — a merge changes node/edge counts the force graph otherwise
  // wouldn't know to reload.
  const [graphVersion, setGraphVersion] = useState(0);
  const [selectedNode, setSelectedNode] = useState<GraphData["nodes"][number] | null>(null);

  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <Link href="/" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
        ← Back
      </Link>
      <h1 className="mt-4 font-heading text-3xl font-bold tracking-tight text-foreground">Concept Graph</h1>
      <div className="mt-6">
        <ReviewQueuePanel
          onResolved={() => {
            setGraphVersion((v) => v + 1);
            // A resolved merge may have removed the currently-selected
            // concept from graph.db entirely — drop the selection so
            // WikiPagePanel doesn't keep showing a concept that no longer
            // exists (its fetch effect keys on node identity, not on
            // graphVersion, so it wouldn't otherwise know to refetch).
            setSelectedNode(null);
          }}
        />
      </div>
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <ConceptGraphView key={graphVersion} onSelectNode={setSelectedNode} />
        </div>
        <div className="lg:col-span-3">
          <WikiPagePanel node={selectedNode} />
        </div>
      </div>
    </main>
  );
}
