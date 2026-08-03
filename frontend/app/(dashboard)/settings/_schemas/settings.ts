export type DigestScope = "ALL" | "ABSENT_ONLY";

export interface NotificationSettings {
  branch_id: string;
  daily_digest_enabled: boolean;
  daily_digest_scope: DigestScope;
}

export interface NotificationSettingsUpdate {
  daily_digest_enabled?: boolean;
  daily_digest_scope?: DigestScope;
}
