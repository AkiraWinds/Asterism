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
    <div className="mt-6 rounded-lg border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="font-heading text-xl font-semibold text-foreground">{ACTION_LABELS[triage.action]}</span>
        <span className="text-sm text-muted-foreground">Score {triage.score}/100</span>
      </div>
      <p className="mt-2 text-sm text-foreground">{triage.reason}</p>
      <dl className="mt-3 flex gap-6 text-xs text-muted-foreground">
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
