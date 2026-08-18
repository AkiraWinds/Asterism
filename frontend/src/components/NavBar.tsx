import Link from "next/link";

// Minimal persistent top nav — the unified workspace at `/` absorbed the old
// separate home/radar pages, so this is the only way left to reach the
// concept graph page. See
// docs/superpowers/specs/2026-08-18-unified-reader-layout-design.md.
export function NavBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
      <Link href="/" className="font-heading text-lg font-bold tracking-tight text-foreground">
        Asterism
      </Link>
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground hover:underline">
          Library
        </Link>
        <Link href="/graph" className="text-muted-foreground hover:text-foreground hover:underline">
          Graph
        </Link>
      </nav>
    </header>
  );
}
