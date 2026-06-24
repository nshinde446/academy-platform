"use client";

import { Label } from "@/components/ui/label";

interface SubjectPickerProps {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}

/**
 * Toggle-chip multiselect for assigning subjects to a teacher. Subjects drive
 * the Subject→Teacher schedule lock — a teacher can only be scheduled for
 * subjects they're assigned here. Names are branch-wide and map to every
 * matching subject row across courses.
 */
export function SubjectPicker({
  options,
  selected,
  onChange,
}: SubjectPickerProps) {
  function toggle(name: string) {
    onChange(
      selected.includes(name)
        ? selected.filter((s) => s !== name)
        : [...selected, name]
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label>Subjects taught</Label>
      {options.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No subjects exist in this branch yet. Create courses/subjects first,
          then assign them here.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {options.map((name) => {
              const active = selected.includes(name);
              return (
                <button
                  key={name}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggle(name)}
                  className={
                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors " +
                    (active
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-700"
                      : "border-input bg-background text-muted-foreground hover:bg-accent")
                  }
                >
                  {name}
                </button>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground">
            Only subjects selected here let this teacher be scheduled for that
            subject.
          </p>
        </>
      )}
    </div>
  );
}
