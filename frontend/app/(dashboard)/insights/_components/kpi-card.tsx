"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface KpiCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "success" | "warning" | "destructive";
}

const TONE_CLASS: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  destructive: "text-destructive",
};

export function KpiCard({ label, value, hint, tone = "default" }: KpiCardProps) {
  return (
    <Card size="sm" className="min-w-0">
      <CardHeader>
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-3xl font-semibold ${TONE_CLASS[tone]}`}>
          {value}
        </div>
        {hint && (
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        )}
      </CardContent>
    </Card>
  );
}
