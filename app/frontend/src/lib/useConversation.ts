import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { GenieMessage, MessageStatus } from "../api/types";

const TERMINAL: MessageStatus[] = ["COMPLETED", "EMPTY", "FAILED", "CANCELLED", "EXPIRED"];
const POLL_INTERVAL_MS = 1200;
const MAX_POLLS = 50; // ~60s bounded polling before we surface a timeout.

export interface Turn {
  id: string;
  question: string;
  message: GenieMessage | null;
  state: "pending" | "done" | "error" | "timeout";
  error?: string;
}

function newId(): string {
  return Math.random().toString(36).slice(2);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function useConversation() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const conversationId = useRef<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const cancelled = useRef(false);

  const patchTurn = useCallback((id: string, patch: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const runPolling = useCallback(
    async (turnId: string, convId: string, messageId: string) => {
      for (let i = 0; i < MAX_POLLS; i++) {
        if (cancelled.current) return;
        await sleep(POLL_INTERVAL_MS);
        if (cancelled.current) return;
        let msg: GenieMessage;
        try {
          msg = await api.getMessage(convId, messageId);
        } catch (err) {
          patchTurn(turnId, {
            state: "error",
            error: err instanceof ApiError ? err.message : "Something went wrong.",
          });
          return;
        }
        if (TERMINAL.includes(msg.status)) {
          patchTurn(turnId, {
            message: msg,
            state: msg.status === "FAILED" ? "error" : "done",
            error: msg.status === "FAILED" ? msg.error ?? undefined : undefined,
          });
          return;
        }
        patchTurn(turnId, { message: msg });
      }
      patchTurn(turnId, {
        state: "timeout",
        error: "Genie is taking longer than expected. Please try again.",
      });
    },
    [patchTurn],
  );

  const ask = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || busy) return;
      cancelled.current = false;
      setBusy(true);
      const turnId = newId();
      setTurns((prev) => [...prev, { id: turnId, question: q, message: null, state: "pending" }]);

      try {
        const created = conversationId.current
          ? await api.followUp(conversationId.current, q)
          : await api.startConversation(q);
        conversationId.current = created.conversation_id;
        setActiveConversationId(created.conversation_id);
        await runPolling(turnId, created.conversation_id, created.message_id);
      } catch (err) {
        patchTurn(turnId, {
          state: "error",
          error: err instanceof ApiError ? err.message : "Unable to reach Genie. Please retry.",
        });
      } finally {
        setBusy(false);
      }
    },
    [busy, patchTurn, runPolling],
  );

  const retryLast = useCallback(async () => {
    const last = turns[turns.length - 1];
    if (!last || busy) return;
    setTurns((prev) => prev.slice(0, -1));
    await ask(last.question);
  }, [turns, busy, ask]);

  const reset = useCallback(() => {
    cancelled.current = true;
    conversationId.current = null;
    setActiveConversationId(null);
    setTurns([]);
    setBusy(false);
  }, []);

  return { turns, busy, ask, retryLast, reset, conversationId: activeConversationId };
}
