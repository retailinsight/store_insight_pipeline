import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SmartActionCard, { SmartAction } from "./SmartActionCard";

// NOTE: this component test requires @testing-library/react,
// @testing-library/jest-dom, and jsdom. Install them before running.

vi.mock("@/contexts/SmartActionsContext", () => ({
  useSmartActions: () => ({
    actions: [],
    actionStates: new Map(),
    isLoading: false,
    error: null,
    updateActionStatus: vi.fn(),
    removeAction: vi.fn(),
    getActionStatus: () => "pending",
    getVisibleActions: () => [],
    getActionsByStatus: () => [],
  }),
}));

const baseAction: SmartAction = {
  id: 1,
  title: "Test action",
  description: "Do this thing.",
  bullets: ["Bullet one.", "Bullet two."],
  recommendedAction: "Recommended step.",
};

describe("SmartActionCard", () => {
  it("renders the cost if not actioned panel", () => {
    const action: SmartAction = {
      ...baseAction,
      costIfNotFixed:
        "If this continues, the store could lose approximately £1,234.56 in the next 4 weeks.",
    };

    render(<SmartActionCard action={action} />);

    expect(
      screen.getByText(/cost if not actioned/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/If this continues, the store could lose approximately/i),
    ).toBeInTheDocument();
    expect(screen.getByText("£1,234.56")).toBeInTheDocument();
  });

  it("shows a placeholder when costIfNotFixed is missing", () => {
    const action: SmartAction = {
      ...baseAction,
      costIfNotFixed: undefined,
    };

    render(<SmartActionCard action={action} />);

    expect(
      screen.getByText(/cost if not actioned/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No projected cost available."),
    ).toBeInTheDocument();
  });

  it("renders the cost panel alongside the existing warning block", () => {
    const costText =
      "If this continues, the store could lose approximately £500 in the next 4 weeks.";
    const action: SmartAction = {
      ...baseAction,
      warning: costText,
      costIfNotFixed: costText,
    };

    render(<SmartActionCard action={action} />);

    const warningBlock = screen.getByTestId("action-card-warning");
    const costPanel = screen.getByTestId("action-card-cost-if-not-actioned");

    expect(warningBlock).toBeInTheDocument();
    expect(costPanel).toBeInTheDocument();
    expect(warningBlock.textContent).toContain(costText);
    expect(costPanel.textContent).toContain(costText);
  });
});
