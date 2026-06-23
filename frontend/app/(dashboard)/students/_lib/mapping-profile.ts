// T5 — reusable column-mapping profile. A returning school's export keeps the
// same odd headers every term, so we remember the last applied file-header →
// field-key map per branch (localStorage) and offer it as the starting point on
// the next upload. One profile per branch keeps the UX simple.

export type ColumnMap = Record<string, string>;

function storageKey(branchId: string): string {
  return `students:column-map:${branchId}`;
}

export function loadMappingProfile(branchId: string): ColumnMap | null {
  try {
    const raw = localStorage.getItem(storageKey(branchId));
    return raw ? (JSON.parse(raw) as ColumnMap) : null;
  } catch {
    return null;
  }
}

export function saveMappingProfile(branchId: string, map: ColumnMap): void {
  localStorage.setItem(storageKey(branchId), JSON.stringify(map));
}

export function clearMappingProfile(branchId: string): void {
  localStorage.removeItem(storageKey(branchId));
}
