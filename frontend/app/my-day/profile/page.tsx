import { UserRound } from "lucide-react";
import { PortalPlaceholder } from "@/components/layout/portal-placeholder";

export default function PortalProfilePage() {
  return (
    <PortalPlaceholder
      title="Profile"
      description="Your profile and employment details, with self-service editing for your contact information (phone, email, emergency contact)."
      icon={UserRound}
    />
  );
}
