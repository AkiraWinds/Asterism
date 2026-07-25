import Link from "next/link";
import { getSource } from "@/lib/api";

export default async function SourcePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const source = await getSource(id);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link
        href="/"
        className="text-sm text-neutral-500 hover:text-neutral-800 hover:underline dark:text-neutral-400 dark:hover:text-neutral-100"
      >
        ← Back
      </Link>

      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
        {source.title}
      </h1>

      <pre className="mt-6 whitespace-pre-wrap rounded-lg border border-neutral-200 bg-white p-5 text-sm leading-relaxed text-neutral-800 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200">
        {source.content}
      </pre>
    </main>
  );
}
