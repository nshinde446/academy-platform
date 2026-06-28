import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toast, Toaster, useToast } from "@/components/ui/toast";

// useToast() must run inside the provider, so wrap the consumer too.
function App() {
  return (
    <Toast.Provider>
      <Inner />
      <Toaster />
    </Toast.Provider>
  );
}

function Inner() {
  const toast = useToast();
  return (
    <>
      <button onClick={() => toast.success("Saved", "Draft stored.")}>
        fire success
      </button>
      <button onClick={() => toast.error("Boom")}>fire error</button>
    </>
  );
}

describe("toast", () => {
  it("shows a success toast with title + description on demand", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "fire success" }));

    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Draft stored.")).toBeInTheDocument();
  });

  it("shows an error toast", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "fire error" }));
    expect(await screen.findByText("Boom")).toBeInTheDocument();
  });
});
