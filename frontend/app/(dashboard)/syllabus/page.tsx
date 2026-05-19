"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { Input } from "@/components/ui/input";
import {
  useChaptersBySubjects,
  useCourses,
  useImportSyllabus,
  useSubjectsForCourse,
  useSubtopicsByTopics,
  useTopicsByChapters,
} from "./_hooks/use-syllabus";
import type {
  ChapterResponse,
  SubtopicResponse,
  TopicResponse,
  TreeChapter,
  TreeSubject,
  TreeTopic,
} from "./_schemas/syllabus";
import { SyllabusTree } from "./_components/syllabus-tree";
import { ImportSyllabusDialog } from "./_components/import-syllabus-dialog";

function flattenQueryData<T>(
  queries: { data?: T[] | undefined }[]
): T[] {
  const out: T[] = [];
  for (const q of queries) {
    if (q.data) out.push(...q.data);
  }
  return out;
}

export default function SyllabusPage() {
  const user = useUserStore((s) => s.user);
  const branchId = user?.branch_roles?.[0]?.branch_id;

  const [courseId, setCourseId] = useState("");
  const [search, setSearch] = useState("");

  const coursesQuery = useCourses(branchId);
  const courses = coursesQuery.data ?? [];

  // Default to the first course once loaded.
  const effectiveCourseId =
    courseId || (courses.length > 0 ? courses[0].id : "");

  const subjectsQuery = useSubjectsForCourse(branchId, effectiveCourseId);
  const subjects = subjectsQuery.data ?? [];

  const subjectIds = useMemo(() => subjects.map((s) => s.id), [subjects]);
  const chapterQueries = useChaptersBySubjects(branchId, subjectIds);
  const chapters: ChapterResponse[] = useMemo(
    () => flattenQueryData(chapterQueries),
    [chapterQueries]
  );

  const chapterIds = useMemo(() => chapters.map((c) => c.id), [chapters]);
  const topicQueries = useTopicsByChapters(branchId, chapterIds);
  const topics: TopicResponse[] = useMemo(
    () => flattenQueryData(topicQueries),
    [topicQueries]
  );

  const topicIds = useMemo(() => topics.map((t) => t.id), [topics]);
  const subtopicQueries = useSubtopicsByTopics(branchId, topicIds);
  const subtopics: SubtopicResponse[] = useMemo(
    () => flattenQueryData(subtopicQueries),
    [subtopicQueries]
  );

  const tree: TreeSubject[] = useMemo(() => {
    const subtopicsByTopic = new Map<string, SubtopicResponse[]>();
    for (const st of subtopics) {
      const bucket = subtopicsByTopic.get(st.topic_id) ?? [];
      bucket.push(st);
      subtopicsByTopic.set(st.topic_id, bucket);
    }
    const topicsByChapter = new Map<string, TreeTopic[]>();
    for (const t of topics) {
      const bucket = topicsByChapter.get(t.chapter_id) ?? [];
      bucket.push({
        id: t.id,
        name: t.name,
        subtopics: subtopicsByTopic.get(t.id) ?? [],
      });
      topicsByChapter.set(t.chapter_id, bucket);
    }
    const chaptersBySubject = new Map<string, TreeChapter[]>();
    for (const c of chapters) {
      const bucket = chaptersBySubject.get(c.subject_id) ?? [];
      bucket.push({
        id: c.id,
        name: c.name,
        topics: topicsByChapter.get(c.id) ?? [],
      });
      chaptersBySubject.set(c.subject_id, bucket);
    }
    return subjects.map((s) => ({
      id: s.id,
      name: s.name,
      chapters: chaptersBySubject.get(s.id) ?? [],
    }));
  }, [subjects, chapters, topics, subtopics]);

  const importMutation = useImportSyllabus();
  const treeLoading =
    subjectsQuery.isLoading ||
    chapterQueries.some((q) => q.isLoading) ||
    topicQueries.some((q) => q.isLoading) ||
    subtopicQueries.some((q) => q.isLoading);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Syllabus Manager</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Browse the syllabus tree for each course. Import an .xlsx to seed
            or extend it — re-imports merge by name and never duplicate nodes.
          </p>
        </div>
        <ImportSyllabusDialog
          courses={courses}
          defaultCourseId={effectiveCourseId}
          onImport={(params) =>
            importMutation.mutateAsync({
              courseId: params.courseId,
              file: params.file,
            })
          }
          isPending={importMutation.isPending}
        />
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          aria-label="Course"
          value={effectiveCourseId}
          onChange={(e) => setCourseId(e.target.value)}
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm sm:max-w-xs"
          disabled={courses.length === 0}
        >
          {courses.length === 0 ? (
            <option value="">No courses yet</option>
          ) : (
            courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))
          )}
        </select>
        <Input
          placeholder="Search nodes (auto-expands matches)..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full sm:max-w-sm"
        />
      </div>

      {/* Content */}
      {!effectiveCourseId ? (
        <p className="text-muted-foreground text-sm">
          Create a course first, then import a syllabus for it.
        </p>
      ) : treeLoading ? (
        <p className="text-muted-foreground text-sm">Loading syllabus...</p>
      ) : subjectsQuery.isError ? (
        <p className="text-destructive text-sm">
          Failed to load syllabus. Make sure the backend is running.
        </p>
      ) : (
        <SyllabusTree subjects={tree} search={search} />
      )}
    </div>
  );
}
