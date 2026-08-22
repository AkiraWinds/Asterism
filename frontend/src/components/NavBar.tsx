"use client";

import Link from "next/link";
import { Minus, Plus } from "@phosphor-icons/react";
import { FONT_SCALE_LEVELS, useFontScale } from "@/components/FontScaleProvider";

// Minimal persistent top nav — the unified workspace at `/` absorbed the old
// separate home/radar pages, so this is the only way left to reach the
// concept graph page. See
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
//
// Also hosts the global font-size control (A-/A+), stepping through
// FONT_SCALE_LEVELS via FontScaleProvider. See
// docs/superpowers/specs/2026-08-21-ui-font-scale-design.md.
export function NavBar() {
  const { fontScale, setFontScale } = useFontScale();

  // fontScale won't exactly match a level right after the initial fetch
  // resolves to a value outside the 5 stops (e.g. a hand-edited
  // config.json) — fall back to the nearest step so the buttons always
  // have somewhere sane to move from.
  const exactIndex = FONT_SCALE_LEVELS.indexOf(fontScale);
  const index =
    exactIndex !== -1
      ? exactIndex
      : FONT_SCALE_LEVELS.reduce(
          (closest, level, i) =>
            Math.abs(level - fontScale) < Math.abs(FONT_SCALE_LEVELS[closest] - fontScale) ? i : closest,
          0
        );

  function step(delta: number) {
    const nextIndex = Math.min(Math.max(index + delta, 0), FONT_SCALE_LEVELS.length - 1);
    setFontScale(FONT_SCALE_LEVELS[nextIndex]);
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
      <Link href="/" className="font-heading text-lg font-bold tracking-tight text-foreground">
        Asterism
      </Link>
      <nav className="flex items-center gap-4 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground hover:underline">
          Library
        </Link>
        <Link href="/graph" className="text-muted-foreground hover:text-foreground hover:underline">
          Graph
        </Link>
        <div className="flex items-center gap-1 border-l border-border pl-4">
          <button
            type="button"
            onClick={() => step(-1)}
            disabled={index === 0}
            aria-label="Decrease font size"
            className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            <Minus size={14} />
          </button>
          <button
            type="button"
            onClick={() => step(1)}
            disabled={index === FONT_SCALE_LEVELS.length - 1}
            aria-label="Increase font size"
            className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
          >
            <Plus size={14} />
          </button>
        </div>
      </nav>
    </header>
  );
}
