import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AskPage } from "./AskPage";

const agent = {
  space_id: "space-123",
  title: "ChicagoPulse",
  description: "**Capabilities:** Monthly neighborhood trends.\n\n**Limitations:** Not real time.",
  warehouse_id: "warehouse-123",
  updated_at: "2026-08-25T15:16:07.929Z",
  space_url: "https://example.databricks.com/genie/rooms/space-123",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AskPage", () => {
  it("shows the agent identity, question input, and suggested starter questions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(agent), { status: 200 }),
    ));
    render(<AskPage />);
    expect(screen.getByLabelText("Your question")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "ChicagoPulse", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Genie/i })).toHaveAttribute(
      "href",
      agent.space_url,
    );
    expect(
      screen.getByRole("button", {
        name: /Which 10 Chicago neighborhoods had the most 311 requests/i,
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("Capabilities and limitations"));
    expect(screen.getByText(/Monthly neighborhood trends/i)).toBeInTheDocument();
    expect(screen.getByText("Last updated")).toBeInTheDocument();
    expect(screen.getByText("Data source")).toBeInTheDocument();
    expect(screen.getByText("City of Chicago open data")).toBeInTheDocument();
    expect(screen.getByText("Analysis scope")).toBeInTheDocument();
    expect(screen.getByText("Completed monthly community-area trends")).toBeInTheDocument();
    expect(screen.queryByText("Space ID")).not.toBeInTheDocument();
    expect(screen.queryByText("Warehouse")).not.toBeInTheDocument();
    expect(screen.queryByText(agent.space_id)).not.toBeInTheDocument();
    expect(screen.queryByText(agent.warehouse_id)).not.toBeInTheDocument();
  });

  it("adds and clears the active Databricks conversation link", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(agent), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-456",
        message_id: "message-789",
        status: "IN_PROGRESS",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-456",
        message_id: "message-789",
        status: "COMPLETED",
        answer_text: "Completed answer.",
        sql: null,
        query_description: null,
        result: null,
        suggested_follow_ups: [],
        is_empty: false,
        error: null,
        provenance: {
          conversation_id: "conversation-456",
          message_id: "message-789",
          attachment_id: null,
          statement_id: null,
          space_id: "space-123",
        },
      }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AskPage />);
    await screen.findByRole("heading", { name: "ChicagoPulse", level: 2 });
    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: "Which neighborhoods led in 311 requests?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const conversationLink = await screen.findByRole("link", { name: /View conversation/i });
    expect(conversationLink).toHaveAttribute(
      "href",
      `${agent.space_url}/chats/conversation-456`,
    );
    const newConversation = screen.getByRole("button", { name: /New Conversation/i });
    await waitFor(() => expect(newConversation).toBeEnabled(), { timeout: 2500 });
    fireEvent.click(newConversation);
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /View conversation/i })).not.toBeInTheDocument();
    });
  });

  it("keeps chat available when agent metadata fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<AskPage />);
    expect(await screen.findByText(/Agent details are temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Your question")).toBeEnabled();
  });

  it("places chart, table, SQL, and provenance in one accessible answer selector", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(agent), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-tabs",
        message_id: "message-tabs",
        status: "IN_PROGRESS",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-tabs",
        message_id: "message-tabs",
        status: "COMPLETED",
        answer_text: "Austin recorded the most requests.",
        sql: "SELECT community_area_name, total_requests FROM neighborhood_requests",
        query_description: "Top community areas by requests",
        result: {
          columns: [
            { name: "community_area_name", type: "string" },
            { name: "total_requests", type: "bigint" },
          ],
          rows: [["Austin", 4820], ["Lake View", 3210]],
          row_count: 2,
          truncated: false,
        },
        suggested_follow_ups: [],
        is_empty: false,
        error: null,
        provenance: {
          conversation_id: "conversation-tabs",
          message_id: "message-tabs",
          attachment_id: "attachment-tabs",
          statement_id: "statement-tabs",
          space_id: "space-123",
        },
      }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AskPage />);
    await screen.findByRole("heading", { name: "ChicagoPulse", level: 2 });
    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: "Which neighborhoods had the most requests?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const chartTab = await screen.findByRole("tab", { name: "Chart" }, { timeout: 3000 });
    const tableTab = screen.getByRole("tab", { name: "Table" });
    const sqlTab = screen.getByRole("tab", { name: "Generated SQL" });
    const detailsTab = screen.getByRole("tab", { name: "Data source & request details" });
    expect(chartTab).toHaveAttribute("aria-selected", "true");

    fireEvent.click(tableTab);
    expect(screen.getByRole("columnheader", { name: "community_area_name" })).toBeInTheDocument();

    fireEvent.click(sqlTab);
    expect(screen.getByText(/SELECT community_area_name, total_requests/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy SQL" })).toBeInTheDocument();

    fireEvent.click(detailsTab);
    expect(screen.getByText("Conversation ID")).toBeInTheDocument();
    expect(screen.getByText("conversation-tabs")).toBeInTheDocument();
  });

  it("submits positive feedback and allows it to be cleared", async () => {
    const completed = {
      conversation_id: "conversation-feedback",
      message_id: "message-feedback",
      status: "COMPLETED",
      answer_text: "A completed answer.",
      sql: null,
      query_description: null,
      result: null,
      suggested_follow_ups: [],
      is_empty: false,
      error: null,
      provenance: {
        conversation_id: "conversation-feedback",
        message_id: "message-feedback",
        attachment_id: null,
        statement_id: null,
        space_id: "space-123",
      },
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(agent), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: completed.conversation_id,
        message_id: completed.message_id,
        status: "IN_PROGRESS",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(completed), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ rating: "POSITIVE" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ rating: "NONE" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AskPage />);
    await screen.findByRole("heading", { name: "ChicagoPulse", level: 2 });
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "Give me an answer" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    const helpful = await screen.findByRole("button", { name: "Helpful answer" }, { timeout: 3000 });
    fireEvent.click(helpful);
    await waitFor(() => expect(helpful).toHaveAttribute("aria-pressed", "true"));
    expect(await screen.findByText("Thanks for your feedback.")).toBeInTheDocument();
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({
      rating: "POSITIVE",
      reason: null,
      comment: null,
    });

    fireEvent.click(helpful);
    await waitFor(() => expect(helpful).toHaveAttribute("aria-pressed", "false"));
    expect(await screen.findByText("Feedback cleared.")).toBeInTheDocument();
  });

  it("requires a reason for negative feedback and sends a normalized form payload", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(agent), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-negative",
        message_id: "message-negative",
        status: "IN_PROGRESS",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        conversation_id: "conversation-negative",
        message_id: "message-negative",
        status: "COMPLETED",
        answer_text: "A completed answer.",
        sql: null,
        query_description: null,
        result: null,
        suggested_follow_ups: [],
        is_empty: false,
        error: null,
        provenance: {
          conversation_id: "conversation-negative",
          message_id: "message-negative",
          attachment_id: null,
          statement_id: null,
          space_id: "space-123",
        },
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ rating: "NEGATIVE" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AskPage />);
    await screen.findByRole("heading", { name: "ChicagoPulse", level: 2 });
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "Give me an answer" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    fireEvent.click(await screen.findByRole("button", { name: "Not a helpful answer" }, { timeout: 3000 }));
    const submit = screen.getByRole("button", { name: "Send feedback" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Incorrect data"));
    fireEvent.change(screen.getByPlaceholderText(/without including personal information/i), {
      target: { value: "The total looks too high." },
    });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    expect(await screen.findByText("Thanks for your feedback.")).toBeInTheDocument();
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({
      rating: "NEGATIVE",
      reason: "INCORRECT_DATA",
      comment: "The total looks too high.",
    });
  });
});
