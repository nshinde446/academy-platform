import { useQueries, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  ChapterResponse,
  CourseOption,
  SubjectResponse,
  SubtopicResponse,
  SyllabusImportSummary,
  TopicResponse,
} from "../_schemas/syllabus";

export const syllabusKeys = {
  courses: (branchId: string) => ["syllabus", "courses", branchId] as const,
  subjects: (branchId: string, courseId: string) =>
    ["syllabus", "subjects", branchId, courseId] as const,
  chapters: (branchId: string, subjectId: string) =>
    ["syllabus", "chapters", branchId, subjectId] as const,
  topics: (branchId: string, chapterId: string) =>
    ["syllabus", "topics", branchId, chapterId] as const,
  subtopics: (branchId: string, topicId: string) =>
    ["syllabus", "subtopics", branchId, topicId] as const,
};

export function useCourses(branchId: string | undefined) {
  return useQuery<CourseOption[]>({
    queryKey: syllabusKeys.courses(branchId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<CourseOption[]>(
        "/api/v1/academic/courses",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useSubjectsForCourse(
  branchId: string | undefined,
  courseId: string | undefined
) {
  return useQuery<SubjectResponse[]>({
    queryKey: syllabusKeys.subjects(branchId ?? "", courseId ?? ""),
    queryFn: async () => {
      const res = await apiClient.get<SubjectResponse[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId, course_id: courseId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!courseId,
  });
}

export function useChaptersBySubjects(
  branchId: string | undefined,
  subjectIds: string[]
) {
  return useQueries({
    queries: subjectIds.map((sid) => ({
      queryKey: syllabusKeys.chapters(branchId ?? "", sid),
      queryFn: async () => {
        const res = await apiClient.get<ChapterResponse[]>(
          "/api/v1/academic/chapters",
          { params: { branch_id: branchId, subject_id: sid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!sid,
    })),
  });
}

export function useTopicsByChapters(
  branchId: string | undefined,
  chapterIds: string[]
) {
  return useQueries({
    queries: chapterIds.map((cid) => ({
      queryKey: syllabusKeys.topics(branchId ?? "", cid),
      queryFn: async () => {
        const res = await apiClient.get<TopicResponse[]>(
          "/api/v1/academic/topics",
          { params: { branch_id: branchId, chapter_id: cid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!cid,
    })),
  });
}

export function useSubtopicsByTopics(
  branchId: string | undefined,
  topicIds: string[]
) {
  return useQueries({
    queries: topicIds.map((tid) => ({
      queryKey: syllabusKeys.subtopics(branchId ?? "", tid),
      queryFn: async () => {
        const res = await apiClient.get<SubtopicResponse[]>(
          "/api/v1/academic/subtopics",
          { params: { branch_id: branchId, topic_id: tid } }
        );
        return res.data;
      },
      enabled: !!branchId && !!tid,
    })),
  });
}

export function useImportSyllabus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      courseId,
      file,
    }: {
      courseId: string;
      file: File;
    }) => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiClient.post<SyllabusImportSummary>(
        "/api/v1/syllabus/import",
        fd,
        {
          params: { course_id: courseId },
          headers: { "Content-Type": "multipart/form-data" },
        }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["syllabus"] });
    },
  });
}
