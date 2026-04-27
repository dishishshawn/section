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

  it("renders the email step", () => {
    render(<SignIn onSignedIn={() => {}} />);
    expect(screen.getByPlaceholderText(/your@email.com/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send code/i })).toBeInTheDocument();
  });

  it("requests a code then shows the code-entry step", async () => {
    render(<SignIn onSignedIn={() => {}} />);
    const input = screen.getByPlaceholderText(/your@email.com/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Send code/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("000000")).toBeInTheDocument();
    });
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/auth/request-code"),
      { email: "user@example.com" },
      expect.objectContaining({ withCredentials: true }),
    );
  });

  it("submits the code and calls onSignedIn", async () => {
    const onSignedIn = vi.fn();
    render(<SignIn onSignedIn={onSignedIn} />);
    fireEvent.change(screen.getByPlaceholderText(/your@email.com/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send code/i }));

    const codeInput = await screen.findByPlaceholderText("000000");
    fireEvent.change(codeInput, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining("/auth/verify-code"),
        { email: "user@example.com", code: "123456" },
        expect.objectContaining({ withCredentials: true }),
      );
    });
    expect(onSignedIn).toHaveBeenCalled();
  });
});
