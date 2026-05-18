// Generated from OpenAPI spec (GET /openapi.json → components.schemas)

export interface AcademicYearResponse {
  id: string;
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
  status: string;
}

export interface AcademicYearCreate {
  branch_id: string;
  name: string;
  start_year: number;
  end_year: number;
}
