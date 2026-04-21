import {
  buildApprovalOutcomeFeedEvent,
  buildApprovalOutcomeInsight,
} from "./approvalOutcome";
import type { PendingApproval } from "./types";

const queueApproval: PendingApproval = {
  action_id: "approval_queue_1",
  action: "close_queue",
  details: { reason: "Capacity reached" },
  shop_id: 41,
};

const shiftApproval: PendingApproval = {
  action_id: "approval_shift_1",
  action: "assign_shift",
  details: {
    user_id: 102,
    date: "2026-04-29",
    start_time: "06:10",
    end_time: "06:40",
  },
  shop_id: 41,
};

describe("approvalOutcome helpers", () => {
  it("builds a queue outcome feed event from executor results", () => {
    const event = buildApprovalOutcomeFeedEvent(
      queueApproval,
      true,
      {
        message: "Approval received. Queue closed.",
        status: "approved",
        tool_results: { message: "Queue closed. Reason: Capacity reached", status: "closed" },
      },
      "2026-04-21T12:00:00Z"
    );

    expect(event).toEqual(
      expect.objectContaining({
        type: "queue_update",
        title: "Queue closed",
        description: "Queue closed. Reason: Capacity reached",
      })
    );
  });

  it("builds a shift outcome insight with schedule context", () => {
    const insight = buildApprovalOutcomeInsight(
      shiftApproval,
      true,
      {
        message: "Approval received. Shift assigned to employee",
        status: "approved",
        tool_results: {
          message: "Shift assigned to employee",
          status: "assigned",
          shift: {
            id: 16,
            user_id: 102,
            clock_in: "2026-04-29T06:10:00",
            clock_out: "2026-04-29T06:40:00",
          },
        },
      },
      "2026-04-21T12:00:00Z"
    );

    expect(insight?.type).toBe("summary");
    expect(insight?.summary?.title).toBe("Shift assigned");
    expect(insight?.summary?.chips).toEqual(
      expect.arrayContaining(["assigned", "Employee 102", "2026-04-29 06:10-06:40"])
    );
  });

  it("returns null when there is no executor result to surface", () => {
    const event = buildApprovalOutcomeFeedEvent(
      queueApproval,
      true,
      {
        message: "Approval received.",
        status: "approved",
      },
      "2026-04-21T12:00:00Z"
    );

    expect(event).toBeNull();
  });
});