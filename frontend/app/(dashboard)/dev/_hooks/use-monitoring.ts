import { useQuery } from "@tanstack/react-query";
import apiClient from "@/services/api-client";

export interface Alert {
  level: "critical" | "warning";
  area: string;
  message: string;
}

export interface DeviceStatusRow {
  dev_id: string;
  last_seen_at: string | null;
  silent_hours: number | null;
  user_count: number | null;
  face_count: number | null;
}

export interface DevMonitoring {
  generated_at: string;
  system: {
    db_size_bytes: number | null;
    connections: number | null;
    counts: Record<string, number>;
  };
  devices: DeviceStatusRow[];
  attendance: { last_punch_at: string | null; punches_today: number };
  backup: {
    created_at: string;
    age_hours: number;
    status: string;
    size_bytes: number;
    offbox: string;
  } | null;
  queue: { pending: number; sent: number };
  alerts: Alert[];
}

// Polls so the dashboard reflects live device/attendance/backup state.
export function useDevMonitoring() {
  return useQuery<DevMonitoring>({
    queryKey: ["dev-monitoring"],
    queryFn: async () => {
      const res = await apiClient.get<DevMonitoring>("/api/v1/dev/monitoring");
      return res.data;
    },
    refetchInterval: 60_000,
  });
}
