// Admin-managed staff accounts. Mirrors backend auth_schemas.

export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  status: string; // "active" | "inactive"
  roles: string[];
}

export interface RoleOption {
  name: string;
  display_name: string;
}

export interface UserCreate {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string | null;
  role: string;
  password: string;
}

export interface UserUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string | null;
  role?: string;
  status?: string;
}
