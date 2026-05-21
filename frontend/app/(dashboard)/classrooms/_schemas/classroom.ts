// Mirrors backend Pydantic schemas in app/modules/classroom/schemas/classroom_schemas.py

export interface ClassroomResponse {
  id: string;
  branch_id: string;
  name: string;
  code: string;
  capacity: number;
  floor: string | null;
  status: string;
}

export interface ClassroomCreate {
  branch_id: string;
  name: string;
  code: string;
  capacity?: number;
  floor?: string | null;
}

export interface ClassroomUpdate {
  name?: string | null;
  code?: string | null;
  capacity?: number | null;
  floor?: string | null;
}
