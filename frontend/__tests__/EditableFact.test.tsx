import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import EditableFact from "../app/components/EditableFact";

vi.mock("axios", () => ({
  default: {
    patch: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

describe("EditableFact", () => {
  it("renders the current value", () => {
    render(
      <EditableFact
        entityType="instrument"
        entityId={1}
        field="grantor"
        value="Acme Minerals"
      />,
    );
    expect(screen.getByText("Acme Minerals")).toBeInTheDocument();
  });

  it("switches to edit mode when the edit button is clicked", () => {
    render(
      <EditableFact
        entityType="instrument"
        entityId={1}
        field="grantor"
        value="Acme Minerals"
      />,
    );
    fireEvent.click(screen.getByLabelText(/Edit grantor/i));
    // The input should now be rendered with the current value as its draft.
    const input = screen.getByDisplayValue("Acme Minerals");
    expect(input).toBeInTheDocument();
    // Cancel button is visible in edit mode.
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
  });
});
