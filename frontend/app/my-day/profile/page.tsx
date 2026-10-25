"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import apiClient, { apiErrorMessage } from "@/services/api-client";

interface Profile {
  name: string;
  employee_code: string;
  department: string | null;
  title: string | null;
  designation: string | null;
  shift_start: string | null;
  shift_end: string | null;
  phone: string | null;
  email: string | null;
}

export default function PortalProfilePage() {
  const router = useRouter();
  const toast = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get<Profile>("/api/v1/me/profile")
      .then((r) => {
        setProfile(r.data);
        setPhone(r.data.phone ?? "");
        setEmail(r.data.email ?? "");
      })
      .catch((e) => {
        const msg = apiErrorMessage(e, "Could not load your profile.");
        if (msg === "PASSWORD_CHANGE_REQUIRED") router.push("/change-password");
        else setError(msg);
      })
      .finally(() => setLoading(false));
  }, [router]);

  const dirty =
    !!profile && (phone !== (profile.phone ?? "") || email !== (profile.email ?? ""));

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!dirty) return;
    setSaving(true);
    try {
      const r = await apiClient.patch<Profile>("/api/v1/me/profile", {
        phone: phone.trim() || null,
        email: email.trim() || null,
      });
      setProfile(r.data);
      setPhone(r.data.phone ?? "");
      setEmail(r.data.email ?? "");
      toast.success("Contact details updated");
    } catch (err) {
      toast.error("Update failed", apiErrorMessage(err, "Check the details and try again."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-xl font-semibold leading-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-xl font-semibold leading-tight">Profile</h1>
        <p className="text-sm text-destructive">{error || "Profile unavailable."}</p>
      </div>
    );
  }

  const shift =
    profile.shift_start || profile.shift_end
      ? `${profile.shift_start ?? "—"}–${profile.shift_end ?? "—"}`
      : "Not set";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold leading-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">
          Your details. You can update your contact information; employment
          details are managed by the office.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Employment — read only */}
        <Card>
          <CardContent className="flex flex-col gap-3 pt-5">
            <h2 className="text-sm font-semibold">Employment</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <ReadField label="Name" value={profile.name} />
              <ReadField label="Employee code" value={profile.employee_code} />
              <ReadField label="Department" value={profile.department ?? "—"} />
              <ReadField label="Designation" value={profile.designation ?? "—"} />
              <ReadField label="Title" value={profile.title ?? "—"} />
              <ReadField label="Shift" value={shift} />
            </dl>
            <p className="text-xs text-muted-foreground">
              To change any of these, contact the office.
            </p>
          </CardContent>
        </Card>

        {/* Contact — editable */}
        <Card>
          <CardContent className="pt-5">
            <form onSubmit={onSave} className="flex flex-col gap-4">
              <h2 className="text-sm font-semibold">Contact details</h2>
              <div className="flex flex-col gap-2">
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  type="tel"
                  inputMode="tel"
                  placeholder="e.g. 9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Personal email</Label>
                <Input
                  id="email"
                  type="email"
                  autoCapitalize="none"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-3">
                <Button type="submit" disabled={!dirty || saving}>
                  {saving ? "Saving…" : "Save changes"}
                </Button>
                {dirty && !saving && (
                  <span className="text-xs text-muted-foreground">Unsaved changes</span>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
