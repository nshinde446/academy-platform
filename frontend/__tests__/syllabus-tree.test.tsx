import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SyllabusTree } from "@/app/(dashboard)/syllabus/_components/syllabus-tree";
import type { TreeSubject } from "@/app/(dashboard)/syllabus/_schemas/syllabus";

const TREE: TreeSubject[] = [
  {
    id: "s1",
    name: "Physics",
    chapters: [
      {
        id: "c1",
        name: "Mechanics",
        topics: [
          {
            id: "t1",
            name: "Newton's Laws",
            subtopics: [
              {
                id: "st1",
                branch_id: "br1",
                academic_year_id: "ay1",
                topic_id: "t1",
                name: "First Law",
                order: 0,
                status: "active",
              },
              {
                id: "st2",
                branch_id: "br1",
                academic_year_id: "ay1",
                topic_id: "t1",
                name: "Second Law",
                order: 1,
                status: "active",
              },
            ],
          },
          { id: "t2", name: "Friction", subtopics: [] },
        ],
      },
      {
        id: "c2",
        name: "Optics",
        topics: [{ id: "t3", name: "Reflection", subtopics: [] }],
      },
    ],
  },
  {
    id: "s2",
    name: "Chemistry",
    chapters: [
      {
        id: "c3",
        name: "Organic",
        topics: [{ id: "t4", name: "Alkanes", subtopics: [] }],
      },
    ],
  },
];

describe("SyllabusTree", () => {
  it("renders an empty state when there are no subjects", () => {
    render(<SyllabusTree subjects={[]} search="" />);
    expect(screen.getByText(/no syllabus yet/i)).toBeInTheDocument();
  });

  it("renders all subjects with chapter counts", () => {
    render(<SyllabusTree subjects={TREE} search="" />);
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("Chemistry")).toBeInTheDocument();
    expect(screen.getByText(/2 chapters/i)).toBeInTheDocument();
    expect(screen.getByText(/1 chapter\b/i)).toBeInTheDocument();
  });

  it("subjects start expanded so chapters are visible", () => {
    render(<SyllabusTree subjects={TREE} search="" />);
    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("Optics")).toBeInTheDocument();
  });

  it("clicking a chapter reveals its topics", async () => {
    const user = userEvent.setup();
    render(<SyllabusTree subjects={TREE} search="" />);
    // Topics start hidden — Newton's Laws not visible yet.
    expect(screen.queryByText("Newton's Laws")).toBeNull();

    await user.click(screen.getByRole("button", { name: /mechanics/i }));
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
    expect(screen.getByText("Friction")).toBeInTheDocument();
  });

  it("clicking a topic reveals its subtopics", async () => {
    const user = userEvent.setup();
    render(<SyllabusTree subjects={TREE} search="" />);
    await user.click(screen.getByRole("button", { name: /mechanics/i }));
    await user.click(screen.getByRole("button", { name: /newton's laws/i }));
    expect(screen.getByText("First Law")).toBeInTheDocument();
    expect(screen.getByText("Second Law")).toBeInTheDocument();
  });

  it("search filters out non-matching subjects and auto-expands matches", () => {
    render(<SyllabusTree subjects={TREE} search="alkanes" />);
    expect(screen.queryByText("Physics")).toBeNull();
    expect(screen.getByText("Chemistry")).toBeInTheDocument();
    expect(screen.getByText("Organic")).toBeInTheDocument();
    // Topic visible without manual expansion because forceOpen is on.
    expect(screen.getByText("Alkanes")).toBeInTheDocument();
  });

  it("search at the subtopic level surfaces the full ancestor chain", () => {
    render(<SyllabusTree subjects={TREE} search="second law" />);
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
    expect(screen.getByText("Second Law")).toBeInTheDocument();
    // First Law was pruned because the topic-name itself didn't match.
    expect(screen.queryByText("First Law")).toBeNull();
  });

  it("shows a 'no matches' message when search has no hits", () => {
    render(<SyllabusTree subjects={TREE} search="zzzz" />);
    expect(screen.getByText(/no syllabus nodes match/i)).toBeInTheDocument();
  });
});
