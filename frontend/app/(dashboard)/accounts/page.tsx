"use client";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";

// Placeholder for the fees/accounts module. Scaffolded now (per the RBAC spec —
// the Accounts role's home) so the nav entry and route exist; the fees features
// land in a later increment.
export default function AccountsPage() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Accounts"
        description="Fees & accounts. This module is being set up — features are coming soon."
      />
      <Card>
        <CardContent>
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <p className="text-lg font-medium">Accounts module coming soon</p>
            <p className="max-w-md text-sm text-muted-foreground">
              This is where fees and accounts will live. It&apos;s scaffolded as
              the home for the Accounts role; the fees features will be built out
              next.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
