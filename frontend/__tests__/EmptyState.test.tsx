import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import EmptyState from "../app/components/EmptyState";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(
      <EmptyState
        title="No projects yet"
        description="Open your first file above."
      />
    );
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByText("Open your first file above.")).toBeInTheDocument();
  });

  it("fires primaryAction.onClick when the primary button is pressed", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="No projects yet"
        description="Create one."
        primaryAction={{ label: "Create your first project", onClick }}
      />
    );
    const btn = screen.getByRole("button", { name: /Create your first project/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders a secondary action when provided", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="No projects yet"
        primaryAction={{ label: "Create", onClick: () => {} }}
        secondaryAction={{ label: "Try with sample deed", onClick }}
      />
    );
    const btn = screen.getByRole("button", { name: /Try with sample deed/i });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
