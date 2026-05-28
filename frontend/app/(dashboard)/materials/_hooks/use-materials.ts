import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/api-client";
import type {
  MaterialFacetCounts,
  MaterialListResponse,
  MaterialResponse,
  MaterialUploadFields,
} from "../_schemas/material";

export interface MaterialListFilters {
  academic_year_id?: string;
  class_label?: string;
  subject_id?: string;
  category?: string;
  exam_type?: string;
  batch_id?: string;
  search?: string;
}

export const materialKeys = {
  all: ["materials"] as const,
  list: (branchId: string, filters: MaterialListFilters) =>
    [...materialKeys.all, "list", branchId, filters] as const,
  facets: (branchId: string, filters: MaterialListFilters) =>
    [...materialKeys.all, "facets", branchId, filters] as const,
  detail: (id: string) => [...materialKeys.all, "detail", id] as const,
};

function buildParams(branchId: string, filters: MaterialListFilters) {
  const params: Record<string, string | number> = {
    branch_id: branchId,
    limit: 200,
  };
  if (filters.academic_year_id) params.academic_year_id = filters.academic_year_id;
  if (filters.class_label) params.class_label = filters.class_label;
  if (filters.subject_id) params.subject_id = filters.subject_id;
  if (filters.category) params.category = filters.category;
  if (filters.exam_type) params.exam_type = filters.exam_type;
  if (filters.batch_id) params.batch_id = filters.batch_id;
  if (filters.search) params.search = filters.search;
  return params;
}

export function useMaterialList(
  branchId: string | undefined,
  filters: MaterialListFilters,
) {
  return useQuery<MaterialListResponse>({
    queryKey: materialKeys.list(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<MaterialListResponse>(
        "/api/v1/materials",
        { params: buildParams(branchId!, filters) },
      );
      return res.data;
    },
    enabled: !!branchId,
    // Ingest runs as a backend BackgroundTask. Poll every 3s while any
    // material is mid-extraction so the status badge + question count
    // update live, then stop polling once nothing is ingesting.
    refetchInterval: (query) => {
      const anyIngesting = query.state.data?.items?.some(
        (m) => m.ingest_status === "ingesting",
      );
      return anyIngesting ? 3000 : false;
    },
  });
}

export function useMaterialFacets(
  branchId: string | undefined,
  filters: MaterialListFilters,
) {
  return useQuery<MaterialFacetCounts>({
    queryKey: materialKeys.facets(branchId ?? "", filters),
    queryFn: async () => {
      const res = await apiClient.get<MaterialFacetCounts>(
        "/api/v1/materials/facets",
        { params: buildParams(branchId!, filters) },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

interface UploadInput {
  file: File;
  fields: MaterialUploadFields;
}

export function useUploadMaterial(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, fields }: UploadInput) => {
      const form = new FormData();
      form.append("file", file);
      form.append("academic_year_id", fields.academic_year_id);
      form.append("class_label", fields.class_label);
      form.append("subject_id", fields.subject_id);
      form.append("category", fields.category);
      if (fields.exam_types.length > 0) {
        form.append("exam_types", fields.exam_types.join(","));
      }
      if (fields.batch_ids?.length) {
        form.append("batch_ids", fields.batch_ids.join(","));
      }
      if (fields.topic) form.append("topic", fields.topic);
      if (fields.description) form.append("description", fields.description);
      const res = await apiClient.post<MaterialResponse>(
        "/api/v1/materials",
        form,
        {
          params: { branch_id: branchId },
          headers: { "Content-Type": "multipart/form-data" },
        },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: materialKeys.all });
    },
  });
}

export function useDeleteMaterial(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (materialId: string) => {
      await apiClient.delete(`/api/v1/materials/${materialId}`, {
        params: { branch_id: branchId },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: materialKeys.all });
    },
  });
}

// ── Reference data hooks (subjects, batches, academic years) ─────────────

export interface SubjectSummary {
  id: string;
  name: string;
  code: string;
  academic_year_id: string;
  course_id: string;
}

export function useSubjects(branchId: string | undefined) {
  return useQuery<SubjectSummary[]>({
    queryKey: ["academic", "subjects", "all", branchId],
    queryFn: async () => {
      const res = await apiClient.get<SubjectSummary[]>(
        "/api/v1/academic/subjects",
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export interface AcademicYearSummary {
  id: string;
  name: string;
  start_year: number;
  end_year: number;
}

export function useAcademicYears(branchId: string | undefined) {
  return useQuery<AcademicYearSummary[]>({
    queryKey: ["academic", "years", branchId],
    queryFn: async () => {
      const res = await apiClient.get<AcademicYearSummary[]>(
        "/api/v1/academic/academic-years",
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    enabled: !!branchId,
  });
}

export interface BatchSummary {
  id: string;
  name: string;
  code: string;
}

export function useBatches(branchId: string | undefined) {
  return useQuery<BatchSummary[]>({
    queryKey: ["batches", "list", branchId],
    queryFn: async () => {
      const res = await apiClient.get<BatchSummary[]>("/api/v1/batches", {
        params: { branch_id: branchId, limit: 200 },
      });
      return res.data;
    },
    enabled: !!branchId,
  });
}

export function useIngestMaterial(branchId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (materialId: string) => {
      const res = await apiClient.post<MaterialResponse>(
        `/api/v1/materials/${materialId}/ingest`,
        null,
        { params: { branch_id: branchId } },
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: materialKeys.all });
    },
  });
}
