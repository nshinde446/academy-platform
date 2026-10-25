import { CalendarOff } from "lucide-react";
import { PortalPlaceholder } from "@/components/layout/portal-placeholder";

export default function PortalLeavePage() {
  return (
    <PortalPlaceholder
      title="Leave"
      description="Apply for leave and track your requests. Each request goes to your academic head for approval before it affects the timetable."
      icon={CalendarOff}
    />
  );
}
