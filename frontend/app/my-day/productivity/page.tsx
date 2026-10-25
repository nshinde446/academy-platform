import { BarChart3 } from "lucide-react";
import { PortalPlaceholder } from "@/components/layout/portal-placeholder";

export default function PortalProductivityPage() {
  return (
    <PortalPlaceholder
      title="Productivity"
      description="Your lectures taken, on-time %, attendance, late minutes and DPP coverage — charted week, month, quarter and year."
      icon={BarChart3}
    />
  );
}
