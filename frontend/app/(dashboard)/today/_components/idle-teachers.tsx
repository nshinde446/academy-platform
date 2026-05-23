"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { RosterIdleTeacher } from "../_schemas/roster";

interface IdleTeachersProps {
  teachers: RosterIdleTeacher[];
}

export function IdleTeachers({ teachers }: IdleTeachersProps) {
  const [open, setOpen] = useState(false);
  if (teachers.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 border-t pt-3 text-sm text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>
          {teachers.length} teacher{teachers.length !== 1 ? "s" : ""} with no
          activity today
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "hide" : "show"}
        </Button>
      </div>
      {open && (
        <div className="flex flex-wrap gap-2 pl-6">
          {teachers.map((t) => (
            <span
              key={t.teacher_id}
              className="rounded-md border px-2 py-0.5 text-xs"
            >
              {t.first_name} {t.last_name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
