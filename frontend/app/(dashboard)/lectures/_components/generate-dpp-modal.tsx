"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import type {
  BatchSummary,
  LectureResponse,
  SubjectSummary,
  TopicSummary,
} from "../_schemas/lecture";

interface GenerateDppModalProps {
  lecture: LectureResponse | null;
  batches: BatchSummary[];
  subjects: SubjectSummary[];
  topics: TopicSummary[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Override router for testing. */
  pushOverride?: (url: string) => void;
}

type Lean = "lecture" | "review" | "stretch";

const LEAN_LABEL: Record<Lean, string> = {
  lecture: "Just today's lecture topic",
  review: "Add review of weakest topics in batch",
  stretch: "Add a couple of stretch problems",
};

const SELECT_CLASS =
  "flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

function defaultName(topicName: string | undefined, fallback: string): string {
  const base = (topicName ?? fallback).trim();
  if (!base) return "DPP";
  return `DPP — ${base}`;
}

export function GenerateDppModal({
  lecture,
  batches,
  subjects,
  topics,
  open,
  onOpenChange,
  pushOverride,
}: GenerateDppModalProps) {
  const router = useRouter();
  const push = pushOverride ?? ((url: string) => router.push(url));

  const batch = useMemo(
    () => batches.find((b) => b.id === lecture?.batch_id),
    [batches, lecture],
  );
  const subject = useMemo(
    () => subjects.find((s) => s.id === lecture?.subject_id),
    [subjects, lecture],
  );
  const topic = useMemo(
    () => topics.find((t) => t.id === lecture?.topic_id),
    [topics, lecture],
  );

  const [numQs, setNumQs] = useState("15");
  const [duration, setDuration] = useState("30 min");
  const [releaseAt, setReleaseAt] = useState("");
  const [lean, setLean] = useState<Lean>("lecture");
  const [name, setName] = useState(
    defaultName(topic?.name, subject?.name ?? "Lecture"),
  );

  function handleSubmit() {
    if (!lecture) return;
    const params = new URLSearchParams();
    params.set("paper_type", "DPP");
    params.set("batch_id", lecture.batch_id);
    params.set("subject_id", lecture.subject_id);
    params.set("name", name.trim() || defaultName(topic?.name, subject?.name ?? "Lecture"));
    params.set("num_qs", numQs);
    params.set("lean", lean);
    params.set("source_lecture_id", lecture.id);
    if (duration) params.set("duration", duration);
    if (releaseAt) params.set("release_at", releaseAt);
    push(`/papers?${params.toString()}`);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-xl">
        <div className="mb-4">
          <DialogTitle>✦ Generate DPP for completed lecture</DialogTitle>
          <DialogDescription>
            We&apos;ll open the paper composer pre-filled with this lecture&apos;s
            subject, topic and batch. You stay in control of the question pick.
          </DialogDescription>
        </div>

        <div className="flex flex-col gap-3 text-sm">
          <div
            className="flex flex-col gap-1 rounded-lg bg-muted p-3"
            aria-label="Lecture summary"
          >
            <Row label="Lecture" value={topic?.name ?? "—"} />
            <Row label="Subject" value={subject?.name ?? "—"} />
            <Row label="Batch" value={batch?.name ?? "—"} />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="dpp-num-qs">Number of Qs</Label>
              <Input
                id="dpp-num-qs"
                type="number"
                min={1}
                max={50}
                value={numQs}
                onChange={(e) => setNumQs(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="dpp-duration">Duration</Label>
              <Input
                id="dpp-duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="dpp-release-at">Release at</Label>
              <Input
                id="dpp-release-at"
                type="datetime-local"
                value={releaseAt}
                onChange={(e) => setReleaseAt(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="dpp-name">Draft name</Label>
            <Input
              id="dpp-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="dpp-lean">Lean toward</Label>
            <select
              id="dpp-lean"
              value={lean}
              onChange={(e) => setLean(e.target.value as Lean)}
              className={SELECT_CLASS}
            >
              {(Object.keys(LEAN_LABEL) as Lean[]).map((k) => (
                <option key={k} value={k}>
                  {LEAN_LABEL[k]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <DialogClose
            render={
              <Button type="button" variant="outline" size="sm">
                Cancel
              </Button>
            }
          />
          <Button
            type="button"
            size="sm"
            onClick={handleSubmit}
            disabled={!lecture}
            aria-label="Open composer with this lecture pre-filled"
          >
            Open in composer →
          </Button>
        </div>
      </DialogPopup>
    </Dialog>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
