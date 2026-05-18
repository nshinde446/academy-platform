"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import {
  useAcademicYears,
  useCourses,
  useCreateCourse,
} from "./_hooks/use-courses";
import type { CourseCreate, CourseResponse } from "./_schemas/course";
import { CourseTable } from "./_components/course-table";
import { CourseEmptyState } from "./_components/course-empty-state";
import { CreateCourseDialog } from "./_components/create-course-dialog";

function filterCourses(
  courses: CourseResponse[],
  query: string
): CourseResponse[] {
  if (!query) return courses;
  const q = query.toLowerCase();
  return courses.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.code.toLowerCase().includes(q) ||
      c.description?.toLowerCase().includes(q)
  );
}

export default function CoursesPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const academicYearsQuery = useAcademicYears(branchId);
  const academicYears = academicYearsQuery.data ?? [];
  const [selectedYearId, setSelectedYearId] = useState<string>("");
  const activeYearId = selectedYearId || academicYears[0]?.id;

  const coursesQuery = useCourses(branchId, activeYearId);
  const createMutation = useCreateCourse(branchId, activeYearId);

  const filtered = useMemo(
    () => filterCourses(coursesQuery.data ?? [], debouncedSearch),
    [coursesQuery.data, debouncedSearch]
  );

  async function handleCreate(data: Omit<CourseCreate, "branch_id">) {
    if (!branchId) return;
    await createMutation.mutateAsync({ ...data, branch_id: branchId });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Courses</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage courses offered each academic year
          </p>
        </div>
        <CreateCourseDialog
          academicYearId={activeYearId}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search by name, code, or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
        {academicYears.length > 0 && (
          <select
            value={activeYearId ?? ""}
            onChange={(e) => setSelectedYearId(e.target.value)}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
            aria-label="Academic year"
          >
            {academicYears.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
              </option>
            ))}
          </select>
        )}
        <span className="text-sm text-muted-foreground">
          {filtered.length} course{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Content */}
      {coursesQuery.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading courses...</p>
      ) : coursesQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load courses. Make sure the backend is running.
        </p>
      ) : filtered.length === 0 ? (
        <CourseEmptyState
          hasSearch={!!debouncedSearch}
          hasAcademicYear={!!activeYearId}
        />
      ) : (
        <CourseTable courses={filtered} />
      )}
    </div>
  );
}
