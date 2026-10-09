"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { useBranchId, useUserStore } from "@/store/user-store";
import { FollowUpBoard } from "./_components/follow-up-board";
import { ForecastPanel } from "./_components/forecast-panel";
import { ConfigPanel } from "./_components/config-panel";
import { CreateProfileDialog } from "./_components/create-profile-dialog";
import { FeeProfileDialog } from "./_components/fee-profile-view";

type Tab = "followup" | "forecast" | "config";

const MANAGER_ROLES = new Set(["super_admin", "branch_admin"]);

export default function AccountsPage() {
  const { branchId } = useBranchId();
  const roles = useUserStore((s) => s.user?.roles ?? []);
  const isManager = useMemo(() => roles.some((r) => MANAGER_ROLES.has(r)), [roles]);

  const [tab, setTab] = useState<Tab>("followup");
  const [profileStudent, setProfileStudent] = useState<string | null>(null);

  const tabs: { key: Tab; label: string }[] = [
    { key: "followup", label: "Daily Follow-Up" },
    ...(isManager
      ? ([
          { key: "forecast", label: "Forecast" },
          { key: "config", label: "Course Fees" },
        ] as { key: Tab; label: string }[])
      : []),
  ];
  const active: Tab = tabs.some((t) => t.key === tab) ? tab : "followup";

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Accounts"
        description="Fee collection, installment tracking, daily follow-up calls and collection forecast."
        actions={<CreateProfileDialog branchId={branchId} />}
      />

      {/* Tab switcher */}
      <div className="inline-flex w-fit rounded-lg border p-0.5 text-sm">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-pressed={active === t.key}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              active === t.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {active === "followup" && (
        <FollowUpBoard branchId={branchId} onOpenProfile={(id) => setProfileStudent(id)} />
      )}
      {active === "forecast" && isManager && <ForecastPanel branchId={branchId} />}
      {active === "config" && isManager && <ConfigPanel branchId={branchId} />}

      <FeeProfileDialog branchId={branchId} studentId={profileStudent} onClose={() => setProfileStudent(null)} />
    </div>
  );
}
