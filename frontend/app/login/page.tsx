"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import apiClient, { apiErrorMessage } from "@/services/api-client";
import { useAuthStore } from "@/store/auth-store";
import { isTeacherOnly, useUserStore } from "@/store/user-store";

export default function LoginPage() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const setAuthenticated = useAuthStore((s) => s.setAuthenticated);
  const fetchUser = useUserStore((s) => s.fetchUser);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // One field for everyone: an email (admins/staff) or an employee code
      // (teachers). Route by shape so the server gets the right identifier.
      const payload = identifier.includes("@")
        ? { email: identifier, password }
        : { username: identifier, password };
      const res = await apiClient.post("/api/v1/auth/login", payload);
      setAuthenticated(true);
      await fetchUser();
      // Forced password change wins; then route teachers to their portal.
      if (res.data?.must_change_password) {
        router.push("/change-password");
        return;
      }
      const user = useUserStore.getState().user;
      router.push(isTeacherOnly(user?.roles) ? "/my-day" : "/home");
    } catch (err) {
      setError(apiErrorMessage(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.svg"
            alt=""
            className="mx-auto mb-1 h-11 w-11"
            aria-hidden
          />
          <CardTitle className="text-2xl">Matrix Science Academy</CardTitle>
          <CardDescription>
            <span className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-gold">
              JEE · NEET · MHT-CET · NDA · IISER
            </span>
            <span className="mt-1 block">Sign in to your account</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}
            <div className="flex flex-col gap-2">
              <Label htmlFor="identifier">Email or Employee Code</Label>
              <Input
                id="identifier"
                type="text"
                autoCapitalize="none"
                autoComplete="username"
                placeholder="you@example.com or 91000"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
