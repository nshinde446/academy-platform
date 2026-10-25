import { CalendarDays } from "lucide-react";
import { PortalPlaceholder } from "@/components/layout/portal-placeholder";

export default function PortalAttendancePage() {
  return (
    <PortalPlaceholder
      title="Attendance"
      description="Your attendance history and month-wise grid — in/out times, late minutes, and fines once the day closes."
      icon={CalendarDays}
    />
  );
}
