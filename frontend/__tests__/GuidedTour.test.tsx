import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import GuidedTour, { TOUR_STORAGE_KEY } from "../app/components/GuidedTour";

describe("GuidedTour", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("auto-shows on first visit when no localStorage flag is set", () => {
    render(<GuidedTour />);
    expect(screen.getByTestId("guided-tour")).toBeInTheDocument();
    // first step is shown
    expect(screen.getByText(/Create a project/i)).toBeInTheDocument();
  });

  it("does not render when the localStorage flag is already set", () => {
    window.localStorage.setItem(TOUR_STORAGE_KEY, "1");
    render(<GuidedTour />);
    expect(screen.queryByTestId("guided-tour")).not.toBeInTheDocument();
  });

  it("skip button dismisses the tour and persists localStorage flag", () => {
    render(<GuidedTour />);
    const skip = screen.getByRole("button", { name: /Skip tour/i });
    fireEvent.click(skip);
    expect(screen.queryByTestId("guided-tour")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(TOUR_STORAGE_KEY)).toBe("1");
  });

  it("persists a per-user flag when userKey is provided", () => {
    render(<GuidedTour userKey={42} />);
    const skip = screen.getByRole("button", { name: /Skip tour/i });
    fireEvent.click(skip);
    expect(window.localStorage.getItem(`${TOUR_STORAGE_KEY}:42`)).toBe("1");
  });

  it("advances through steps and finishes on the last Next click", () => {
    render(<GuidedTour />);
    const nextBtn = () => screen.getByRole("button", { name: /Next|Finish/i });
    fireEvent.click(nextBtn()); // step 2
    fireEvent.click(nextBtn()); // step 3
    fireEvent.click(nextBtn()); // step 4 — Finish
    expect(screen.getByRole("button", { name: /Finish/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Finish/i }));
    expect(screen.queryByTestId("guided-tour")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(TOUR_STORAGE_KEY)).toBe("1");
  });
});
