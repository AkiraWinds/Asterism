export function AnalysisSectionError({
  message,
  onRetry,
  retrying,
}: {
  message: string;
  onRetry: () => void;
  retrying: boolean;
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      <p>This section failed to analyze: {message}</p>
      <button
        type="button"
        onClick={onRetry}
        disabled={retrying}
        className="mt-2 rounded-md border border-red-300 px-3 py-1 text-xs font-medium hover:bg-red-100 disabled:opacity-50 dark:border-red-800 dark:hover:bg-red-900"
      >
        {retrying ? "Retrying…" : "Retry"}
      </button>
    </div>
  );
}
