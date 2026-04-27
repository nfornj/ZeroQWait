import React from "react";
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import ThinkingSteps from "./ThinkingSteps";

describe("ThinkingSteps", () => {
  it("shows a compact thinking label while work is in progress", () => {
    render(
      <ThemeProvider theme={createTheme()}>
        <ThinkingSteps
          steps={[
            {
              id: "step_1",
              label: "Checking queue status",
              status: "active",
            },
          ]}
          isComplete={false}
        />
      </ThemeProvider>,
    );

    expect(screen.getByText("Checking queue status")).toBeInTheDocument();
  });

  it("disappears as soon as the stream is complete", () => {
    const { rerender } = render(
      <ThemeProvider theme={createTheme()}>
        <ThinkingSteps
          steps={[
            {
              id: "step_1",
              label: "Checking queue status",
              status: "active",
            },
          ]}
          isComplete={false}
        />
      </ThemeProvider>,
    );

    expect(screen.getByText("Checking queue status")).toBeInTheDocument();

    rerender(
      <ThemeProvider theme={createTheme()}>
        <ThinkingSteps
          steps={[
            {
              id: "step_1",
              label: "Checking queue status",
              status: "completed",
            },
          ]}
          isComplete
        />
      </ThemeProvider>,
    );

    expect(screen.queryByText("Checking queue status")).not.toBeInTheDocument();
  });
});