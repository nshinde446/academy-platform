/**
 * Run a single-item delete across a set of ids, sequentially.
 *
 * We deliberately reuse the existing per-item delete endpoints (which already
 * enforce dependency guards — e.g. "a course with active batches can't be
 * deleted") instead of a blanket cascade. Sequential, not Promise.all, so the
 * backend isn't hammered and the partial result is deterministic.
 *
 * Returns how many succeeded plus the ones that were skipped, with the reason
 * the server gave — so the UI can say "Deleted 12, skipped 3 (have batches)".
 */
export interface BulkDeleteResult {
  deleted: number;
  failed: { id: string; reason: string }[];
}

function reasonFromError(err: unknown): string {
  const e = err as {
    response?: { data?: { error?: { message?: string }; detail?: string } };
    message?: string;
  };
  return (
    e?.response?.data?.error?.message ||
    e?.response?.data?.detail ||
    e?.message ||
    "Delete failed"
  );
}

export async function runBulkDelete(
  ids: string[],
  deleteOne: (id: string) => Promise<unknown>,
): Promise<BulkDeleteResult> {
  const result: BulkDeleteResult = { deleted: 0, failed: [] };
  for (const id of ids) {
    try {
      await deleteOne(id);
      result.deleted += 1;
    } catch (err) {
      result.failed.push({ id, reason: reasonFromError(err) });
    }
  }
  return result;
}

/** One-line human summary of a bulk delete, grouping skips by reason. */
export function summarizeBulkDelete(
  result: BulkDeleteResult,
  noun: string,
): string {
  const plural = (n: number) => (n === 1 ? noun : `${noun}s`);
  if (result.failed.length === 0) {
    return `Deleted ${result.deleted} ${plural(result.deleted)}.`;
  }
  const byReason = new Map<string, number>();
  for (const f of result.failed) {
    byReason.set(f.reason, (byReason.get(f.reason) ?? 0) + 1);
  }
  const skips = [...byReason.entries()]
    .map(([reason, n]) => `${n} (${reason})`)
    .join(", ");
  return `Deleted ${result.deleted} ${plural(result.deleted)}, skipped ${result.failed.length}: ${skips}.`;
}
