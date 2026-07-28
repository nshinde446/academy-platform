// BioMax device-provisioning shapes. Kept in sync with the backend Pydantic
// schemas in app/modules/attendance/schemas/provisioning_schemas.py.
//
// This is the READ-ONLY reconciliation surface: which students are on the
// platform vs mirrored on the device. The push (SET_USER_INFO) flow is a
// separate, capture-gated increment.

export interface ProvisionDevice {
  dev_id: string;
}

export interface ProvisionDevicesResponse {
  // Whether BIOMAX_PROVISIONING_ENABLED is on. When false the reconcile call
  // 503s by design — the UI shows a "dormant" state instead of an error.
  enabled: boolean;
  devices: ProvisionDevice[];
}

export interface ReconcileRow {
  vendor_user_id: string; // device userId == Student.rfid_number
  name: string | null;
  student_id: string | null;
}

export interface ReconcileResponse {
  dev_id: string;
  on_platform_not_on_device: ReconcileRow[]; // need pushing
  on_device_not_on_platform: ReconcileRow[]; // stale/manual device entries
  drift: ReconcileRow[]; // present on both, name differs
}
