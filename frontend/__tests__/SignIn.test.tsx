import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignIn from "../app/components/SignIn";

vi.mock("axios", () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import axios from "axios";

describe("SignIn", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the email form", () => {
    render(<SignIn onSignedIn={() => {}} />);
    expect(screen.getByPlaceholderText(/your@email.com/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send link/i })).toBeInTheDocument();
  });

  it("submits the email and shows confirmation", async () => {
    render(<SignIn onSignedIn={() => {}} />);
    const input = screen.getByPlaceholderText(/your@email.com/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Send link/i }));

    await waitFor(() => {
      expect(screen.getByText(/Check your email/i)).toBeInTheDocument();
    });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/auth/request-link"),
      { email: "user@example.com" },
      expect.objectContaining({ withCredentials: true }),
    );
  });
});
