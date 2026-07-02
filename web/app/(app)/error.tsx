"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
      <h2 className="mb-2 text-lg font-bold">⚠ Une erreur est survenue</h2>
      <p className="mb-4 break-words">{error.message}</p>
      <button
        onClick={reset}
        className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--brand-dark)]"
      >
        Réessayer
      </button>
    </div>
  );
}
