"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { isTeacherOnly, useUserStore } from "@/store/user-store";

export default function ChangePasswordPage() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const fetchUser = useUserStore((s) => s.fetchUser);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await apiClient.post("/api/v1/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      await fetchUser();
      const user = useUserStore.getState().user;
      router.push(isTeacherOnly(user?.roles) ? "/my-day" : "/home");
    } catch (err) {
      setError(apiErrorMessage(err, "Could not change the password."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Set a new password</CardTitle>
          <CardDescription>
            For your security, choose a new password before continuing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && <p className="text-center text-sm text-destructive">{error}</p>}
            <div className="flex flex-col gap-2">
              <Label htmlFor="current">Current (temporary) password</Label>
              <Input id="current" type="password" value={current}
                onChange={(e) => setCurrent(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="next">New password</Label>
              <Input id="next" type="password" value={next} autoComplete="new-password"
                onChange={(e) => setNext(e.target.value)} required minLength={8} />
              <p className="text-xs text-muted-foreground">
                At least 8 characters; not your employee code or old password.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input id="confirm" type="password" value={confirm} autoComplete="new-password"
                onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Saving…" : "Change password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
