import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface SecondarySubjectRow {
  id: string;
  teacher_id: string;
  teacher_name: string;
  subject_id: string;
  subject_name: string;
  batch_id: string;
  batch_name: string;
}

export const secondaryKeys = {
  all: ["secondary-subjects"] as const,
  forTeacher: (branchId: string, teacherId: string) =>
    [...secondaryKeys.all, "teacher", branchId, teacherId] as const,
  forBatch: (branchId: string, batchId: string) =>
    [...secondaryKeys.all, "batch", branchId, batchId] as const,
  catalog: (branchId: string) =>
    [...secondaryKeys.all, "catalog", branchId] as const,
};

/** The academy's teachable subject names (PCMB + the six languages/IT/etc.). */
export function useSubjectCatalog(branchId: string | undefined) {
  return useQuery<string[]>({
    queryKey: secondaryKeys.catalog(branchId!),
    queryFn: async () => {
      const res = await apiClient.get<string[]>(
        "/api/v1/academic/subjects/catalog",
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useSecondaryForTeacher(
  branchId: string | undefined,
  teacherId: string | undefined
) {
  return useQuery<SecondarySubjectRow[]>({
    queryKey: secondaryKeys.forTeacher(branchId!, teacherId!),
    queryFn: async () => {
      const res = await apiClient.get<SecondarySubjectRow[]>(
        "/api/v1/teachers/secondary-subjects",
        { params: { branch_id: branchId, teacher_id: teacherId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!teacherId,
  });
}

export function useSecondaryForBatch(
  branchId: string | undefined,
  batchId: string | undefined
) {
  return useQuery<SecondarySubjectRow[]>({
    queryKey: secondaryKeys.forBatch(branchId!, batchId!),
    queryFn: async () => {
      const res = await apiClient.get<SecondarySubjectRow[]>(
        "/api/v1/teachers/secondary-subjects",
        { params: { branch_id: branchId, batch_id: batchId } }
      );
      return res.data;
    },
    enabled: !!branchId && !!batchId,
  });
}

export function useAssignSecondarySubjects(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: {
      teacherId: string;
      subjectName: string;
      batchIds: string[];
    }) => {
      const res = await apiClient.post<SecondarySubjectRow[]>(
        `/api/v1/teachers/${vars.teacherId}/secondary-subjects`,
        { subject_name: vars.subjectName, batch_ids: vars.batchIds },
        { params: { branch_id: branchId } }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: secondaryKeys.all });
    },
  });
}

export function useRemoveSecondarySubject(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (mappingId: string) => {
      await apiClient.delete(
        `/api/v1/teachers/secondary-subjects/${mappingId}`,
        { params: { branch_id: branchId } }
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: secondaryKeys.all });
    },
  });
}
