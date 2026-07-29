import { Triage } from "@/lib/api";

const ACTION_LABELS: Record<Triage["action"], string> = {
  must_read: "Must read",
  worth_reading: "Worth reading",
  skim: "Skim",
  summary_only: "Summary only",
  skip: "Skip",
};

export function TriageCard({ triage }: { triage: Triage }) {
  return (
    <div className="mt-6 rounded-lg border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between">
        <span className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
          {ACTION_LABELS[triage.action]}
        </span>
        <span className="text-sm text-neutral-500 dark:text-neutral-400">Score {triage.score}/100</span>
      </div>
      <p className="mt-2 text-sm text-neutral-700 dark:text-neutral-300">{triage.reason}</p>
      <dl className="mt-3 flex gap-6 text-xs text-neutral-500 dark:text-neutral-400">
        <div>
          <dt className="uppercase tracking-wide">Read time</dt>
          <dd>{triage.read_time_minutes} min</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Density</dt>
          <dd>{triage.density}/100</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide">Originality</dt>
          <dd>{triage.originality}/100</dd>
        </div>
      </dl>
    </div>
  );
}
