// T7 — roster filters + Saved Views. Filters are a small faceted query; a Saved
// View is just a named snapshot of them. Persisted per branch in localStorage so
// "Pending Payment", "12th NEET" etc. survive reloads without a backend table.

export interface RosterFilters {
  standard: string;
  targetExam: string;
  feesStatus: string;
  batchId: string;
}

export interface SavedView {
  name: string;
  filters: RosterFilters;
}

export const EMPTY_FILTERS: RosterFilters = {
  standard: "",
  targetExam: "",
  feesStatus: "",
  batchId: "",
};

export function hasActiveFilters(f: RosterFilters): boolean {
  return !!(f.standard || f.targetExam || f.feesStatus || f.batchId);
}

function storageKey(branchId: string): string {
  return `students:saved-views:${branchId}`;
}

export function loadSavedViews(branchId: string): SavedView[] {
  try {
    const raw = localStorage.getItem(storageKey(branchId));
    return raw ? (JSON.parse(raw) as SavedView[]) : [];
  } catch {
    return [];
  }
}

function persist(branchId: string, views: SavedView[]): void {
  localStorage.setItem(storageKey(branchId), JSON.stringify(views));
}

/** Insert or replace a view by name; returns the updated list. */
export function upsertSavedView(branchId: string, view: SavedView): SavedView[] {
  const views = loadSavedViews(branchId).filter((v) => v.name !== view.name);
  views.push(view);
  persist(branchId, views);
  return views;
}

export function deleteSavedView(branchId: string, name: string): SavedView[] {
  const views = loadSavedViews(branchId).filter((v) => v.name !== name);
  persist(branchId, views);
  return views;
}
