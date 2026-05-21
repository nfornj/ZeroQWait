import React from "react";
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import ThinkingSteps from "./ThinkingSteps";

describe("ThinkingSteps", () => {
  it("shows a compact thinking label while work is in progress", () => {
    render(
      <ThinkingSteps
        steps={[{ id: "step_1", label: "Checking queue status", status: "active" }]}
        isComplete={false}
      />,
    );
    expect(screen.getByText("Checking queue status")).toBeInTheDocument();
  });

  it("disappears as soon as the stream is complete", () => {
    const { rerender } = render(
      <ThinkingSteps
        steps={[{ id: "step_1", label: "Checking queue status", status: "active" }]}
        isComplete={false}
      />,
    );
    expect(screen.getByText("Checking queue status")).toBeInTheDocument();

    rerender(
      <ThinkingSteps
        steps={[{ id: "step_1", label: "Checking queue status", status: "completed" }]}
        isComplete
      />,
    );
    expect(screen.queryByText("Checking queue status")).not.toBeInTheDocument();
  });
});