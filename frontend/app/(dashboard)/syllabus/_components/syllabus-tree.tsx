"use client";

import { useMemo, useState } from "react";
import type {
  SubtopicResponse,
  TreeChapter,
  TreeSubject,
  TreeTopic,
} from "../_schemas/syllabus";

interface SyllabusTreeProps {
  subjects: TreeSubject[];
  search: string;
}

// Returns the trimmed lowercase query if non-empty, or null.
function activeQuery(search: string): string | null {
  const q = search.trim().toLowerCase();
  return q.length > 0 ? q : null;
}

function matches(name: string, q: string | null): boolean {
  if (!q) return true;
  return name.toLowerCase().includes(q);
}

// Recurse and decide whether a subject/chapter/topic stays in the filtered view.
// A node stays if its own name matches OR any descendant matches; descendants
// that don't match are pruned.
function filterTree(subjects: TreeSubject[], q: string | null): TreeSubject[] {
  if (!q) return subjects;
  const out: TreeSubject[] = [];
  for (const s of subjects) {
    const sMatches = matches(s.name, q);
    const chapters: TreeChapter[] = [];
    for (const c of s.chapters) {
      const cMatches = matches(c.name, q);
      const topics: TreeTopic[] = [];
      for (const t of c.topics) {
        const tMatches = matches(t.name, q);
        const subs = t.subtopics.filter((st) => matches(st.name, q));
        if (tMatches || subs.length > 0) {
          topics.push({
            ...t,
            subtopics: tMatches ? t.subtopics : subs,
          });
        }
      }
      if (cMatches || topics.length > 0) {
        chapters.push({
          ...c,
          topics: cMatches && topics.length === 0 ? c.topics : topics,
        });
      }
    }
    if (sMatches || chapters.length > 0) {
      out.push({
        ...s,
        chapters: sMatches && chapters.length === 0 ? s.chapters : chapters,
      });
    }
  }
  return out;
}

function Highlighted({ text, query }: { text: string; query: string | null }) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query);
  if (idx < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-100 dark:bg-yellow-900/40 rounded px-0.5">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <span
      aria-hidden
      className={`inline-block text-muted-foreground transition-transform ${
        open ? "rotate-90" : ""
      }`}
    >
      ▶
    </span>
  );
}

function SubtopicLeaf({ st, q }: { st: SubtopicResponse; q: string | null }) {
  return (
    <li
      data-testid="subtopic-node"
      className="py-0.5 text-sm text-muted-foreground"
    >
      <span className="mr-2">•</span>
      <Highlighted text={st.name} query={q} />
    </li>
  );
}

function TopicBranch({
  topic,
  q,
  forceOpen,
}: {
  topic: TreeTopic;
  q: string | null;
  forceOpen: boolean;
}) {
  const [open, setOpen] = useState(false);
  const isOpen = forceOpen || open;
  const hasChildren = topic.subtopics.length > 0;
  return (
    <li data-testid="topic-node">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 py-0.5 text-sm hover:underline"
        aria-expanded={isOpen}
      >
        {hasChildren ? <Chevron open={isOpen} /> : <span className="w-3" />}
        <span>
          <Highlighted text={topic.name} query={q} />
        </span>
      </button>
      {isOpen && hasChildren && (
        <ul className="ml-6 mt-0.5">
          {topic.subtopics.map((st) => (
            <SubtopicLeaf key={st.id} st={st} q={q} />
          ))}
        </ul>
      )}
    </li>
  );
}

function ChapterBranch({
  chapter,
  q,
  forceOpen,
}: {
  chapter: TreeChapter;
  q: string | null;
  forceOpen: boolean;
}) {
  const [open, setOpen] = useState(false);
  const isOpen = forceOpen || open;
  const hasChildren = chapter.topics.length > 0;
  return (
    <li data-testid="chapter-node">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 py-1 text-sm font-medium hover:underline"
        aria-expanded={isOpen}
      >
        {hasChildren ? <Chevron open={isOpen} /> : <span className="w-3" />}
        <span>
          <Highlighted text={chapter.name} query={q} />
        </span>
      </button>
      {isOpen && hasChildren && (
        <ul className="ml-6">
          {chapter.topics.map((t) => (
            <TopicBranch
              key={t.id}
              topic={t}
              q={q}
              forceOpen={forceOpen}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function SubjectBranch({
  subject,
  q,
  forceOpen,
}: {
  subject: TreeSubject;
  q: string | null;
  forceOpen: boolean;
}) {
  const [open, setOpen] = useState(true);
  const isOpen = forceOpen || open;
  const hasChildren = subject.chapters.length > 0;
  return (
    <li data-testid="subject-node" className="border-b last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 py-2 text-base font-semibold hover:underline"
        aria-expanded={isOpen}
      >
        {hasChildren ? <Chevron open={isOpen} /> : <span className="w-3" />}
        <span>
          <Highlighted text={subject.name} query={q} />
        </span>
        <span className="ml-auto text-xs font-normal text-muted-foreground">
          {subject.chapters.length} chapter
          {subject.chapters.length === 1 ? "" : "s"}
        </span>
      </button>
      {isOpen && hasChildren && (
        <ul className="ml-6 pb-2">
          {subject.chapters.map((c) => (
            <ChapterBranch
              key={c.id}
              chapter={c}
              q={q}
              forceOpen={forceOpen}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function SyllabusTree({ subjects, search }: SyllabusTreeProps) {
  const q = activeQuery(search);
  const filtered = useMemo(() => filterTree(subjects, q), [subjects, q]);

  if (filtered.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        {q
          ? `No syllabus nodes match "${search}".`
          : "No syllabus yet. Use “Import Syllabus” to load one."}
      </p>
    );
  }

  return (
    <ul
      data-testid="syllabus-tree"
      className="rounded-xl border ring-1 ring-foreground/10 bg-background px-4"
    >
      {filtered.map((s) => (
        <SubjectBranch key={s.id} subject={s} q={q} forceOpen={!!q} />
      ))}
    </ul>
  );
}
