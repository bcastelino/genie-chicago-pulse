import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { FeedbackRating, FeedbackReason, GenieAgent, GenieMessage } from "../api/types";
import { AutoChart } from "../components/lazy";
import { chooseChart } from "../components/chartSpec";
import { CopyButton } from "../components/CopyButton";
import { GenieAgentHeader } from "../components/GenieAgentHeader";
import { LiveServiceErrorState } from "../components/LiveServiceErrorState";
import { ProvenanceContent } from "../components/ProvenanceDetails";
import { ResultTable } from "../components/ResultTable";
import { SqlResultPanel } from "../components/SqlDisclosure";
import { EmptyState, ErrorState, ProgressBar } from "../components/States";
import { SuggestedQuestions } from "../components/SuggestedQuestions";
import {
  IconChart,
  IconCode,
  IconDatabase,
  IconPlus,
  IconSend,
  IconTable,
  IconThumbDown,
  IconThumbUp,
} from "../components/icons";
import { renderMarkdown } from "../lib/markdown";
import type { Turn } from "../lib/useConversation";
import { useConversation } from "../lib/useConversation";
import { isWakeableServiceError } from "../hooks/useLiveServiceRecovery";

const MAX_LEN = 1000;
const MAX_FEEDBACK_COMMENT = 500;

const FEEDBACK_REASONS: { value: FeedbackReason; label: string }[] = [
  { value: "INCORRECT_DATA", label: "Incorrect data" },
  { value: "MISUNDERSTOOD_QUESTION", label: "Misunderstood question" },
  { value: "WRONG_TIME_OR_SCOPE", label: "Wrong time or scope" },
  { value: "POOR_VISUALIZATION", label: "Poor visualization" },
  { value: "OTHER", label: "Other" },
];

function progressLabel(message: GenieMessage | null): string {
  if (!message) return "Sending your question to Genie…";
  return "Genie is analyzing your question and running SQL…";
}

function MessageResult({ message }: { message: GenieMessage }) {
  const result = message.result;
  const spec = result ? chooseChart(result.columns, result.rows) : { kind: "none" as const };
  const canChart = spec.kind !== "none";
  const hasTable = Boolean(result && result.columns.length > 0);
  type ResultView = "chart" | "table" | "sql" | "details";
  const views: { id: ResultView; label: string; icon: typeof IconChart }[] = [
    ...(canChart ? [{ id: "chart" as const, label: "Chart", icon: IconChart }] : []),
    ...(hasTable ? [{ id: "table" as const, label: "Table", icon: IconTable }] : []),
    ...(message.sql ? [{ id: "sql" as const, label: "Generated SQL", icon: IconCode }] : []),
    { id: "details", label: "Data source & request details", icon: IconDatabase },
  ];
  const [view, setView] = useState<ResultView>(canChart ? "chart" : hasTable ? "table" : message.sql ? "sql" : "details");
  const resultViewId = useId();
  const panelId = `${resultViewId}-panel`;

  const selectAdjacentView = (current: ResultView, direction: number) => {
    const currentIndex = views.findIndex((item) => item.id === current);
    const nextIndex = (currentIndex + direction + views.length) % views.length;
    const nextView = views[nextIndex].id;
    setView(nextView);
    window.requestAnimationFrame(() => document.getElementById(`${resultViewId}-${nextView}`)?.focus());
  };

  const isEmpty = message.is_empty || (result && result.row_count === 0);
  return (
    <div className="stack" style={{ gap: "var(--sp-4)" }}>
      {isEmpty && (
      <EmptyState
        title="No matching records"
        message="Genie ran successfully but found no data for this question. Try adjusting the time range or neighborhood."
      />
      )}
      <div className="result-view">
        <div className="result-view__tabs" role="tablist" aria-label="Answer views">
          {views.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                id={`${resultViewId}-${item.id}`}
                className="result-view__tab"
                type="button"
                role="tab"
                aria-selected={view === item.id}
                aria-controls={panelId}
                tabIndex={view === item.id ? 0 : -1}
                onClick={() => setView(item.id)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowRight") {
                    event.preventDefault();
                    selectAdjacentView(item.id, 1);
                  } else if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    selectAdjacentView(item.id, -1);
                  }
                }}
              >
                <Icon size={15} /> {item.label}
              </button>
            );
          })}
        </div>
        <div
          id={panelId}
          className="result-view__panel"
          role="tabpanel"
          aria-labelledby={`${resultViewId}-${view}`}
          tabIndex={0}
        >
          {view === "chart" && result && <AutoChart columns={result.columns} rows={result.rows} spec={spec} />}
          {view === "table" && result && (
            <ResultTable columns={result.columns} rows={result.rows} caption="Genie query result" />
          )}
          {view === "sql" && message.sql && <SqlResultPanel sql={message.sql} />}
          {view === "details" && <ProvenanceContent provenance={message.provenance} />}
          {result?.truncated && (view === "chart" || view === "table") && (
            <p className="help result-view__footnote">
              Showing the first {result.rows.length} rows of {result.row_count}.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function AnswerFeedback({ message }: { message: GenieMessage }) {
  const [rating, setRating] = useState<FeedbackRating>("NONE");
  const [reason, setReason] = useState<FeedbackReason | "">("");
  const [comment, setComment] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const submit = async (
    nextRating: FeedbackRating,
    nextReason: FeedbackReason | null = null,
    nextComment: string | null = null,
  ) => {
    setSubmitting(true);
    setError("");
    setStatus("");
    try {
      const response = await api.sendMessageFeedback(message.conversation_id, message.message_id, {
        rating: nextRating,
        reason: nextReason,
        comment: nextComment,
      });
      setRating(response.rating);
      setShowForm(false);
      if (response.rating !== "NEGATIVE") {
        setReason("");
        setComment("");
      }
      setStatus(response.rating === "NONE" ? "Feedback cleared." : "Thanks for your feedback.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save feedback. Please retry.");
    } finally {
      setSubmitting(false);
    }
  };

  const choosePositive = () => {
    if (rating === "POSITIVE") {
      void submit("NONE");
    } else {
      void submit("POSITIVE");
    }
  };

  const chooseNegative = () => {
    setError("");
    setStatus("");
    if (rating === "NEGATIVE" && !showForm) {
      void submit("NONE");
      return;
    }
    setShowForm(true);
  };

  const trimmedComment = comment.trim();
  const canSubmitNegative = Boolean(reason) && (reason !== "OTHER" || Boolean(trimmedComment));

  return (
    <section className="answer-feedback" aria-label="Answer feedback">
      <div className="answer-feedback__prompt">
        <span>Was this answer helpful?</span>
        <div className="answer-feedback__actions">
          <button
            className="answer-feedback__button"
            type="button"
            aria-label="Helpful answer"
            aria-pressed={rating === "POSITIVE"}
            disabled={submitting}
            onClick={choosePositive}
          >
            <IconThumbUp size={16} />
          </button>
          <button
            className="answer-feedback__button"
            type="button"
            aria-label="Not a helpful answer"
            aria-pressed={rating === "NEGATIVE"}
            aria-expanded={showForm}
            disabled={submitting}
            onClick={chooseNegative}
          >
            <IconThumbDown size={16} />
          </button>
        </div>
      </div>

      {showForm && (
        <form
          className="answer-feedback__form"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmitNegative) {
              void submit("NEGATIVE", reason as FeedbackReason, trimmedComment || null);
            }
          }}
        >
          <fieldset disabled={submitting}>
            <legend>What could be improved?</legend>
            <div className="answer-feedback__reasons">
              {FEEDBACK_REASONS.map((item) => (
                <label key={item.value} className="answer-feedback__reason">
                  <input
                    type="radio"
                    name={`feedback-reason-${message.message_id}`}
                    value={item.value}
                    checked={reason === item.value}
                    onChange={() => setReason(item.value)}
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <label className="field">
            <span>{reason === "OTHER" ? "Comment (required)" : "Comment (optional)"}</span>
            <textarea
              className="textarea answer-feedback__comment"
              rows={3}
              maxLength={MAX_FEEDBACK_COMMENT}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Share a short detail without including personal information."
              disabled={submitting}
            />
          </label>
          <div className="answer-feedback__footer">
            <span className="help">{comment.length}/{MAX_FEEDBACK_COMMENT}</span>
            <div className="row" style={{ gap: "var(--sp-2)" }}>
              <button className="btn btn--ghost btn--sm" type="button" onClick={() => setShowForm(false)} disabled={submitting}>
                Cancel
              </button>
              <button className="btn btn--primary btn--sm" type="submit" disabled={!canSubmitNegative || submitting}>
                {submitting ? "Sending…" : "Send feedback"}
              </button>
            </div>
          </div>
        </form>
      )}

      <div className={`answer-feedback__status ${error ? "answer-feedback__status--error" : ""}`} aria-live="polite">
        {error || status}
      </div>
    </section>
  );
}

function AnswerCard({
  turn,
  onFollowUp,
  onRetry,
  busy,
}: {
  turn: Turn;
  onFollowUp: (q: string) => void;
  onRetry: () => void;
  busy: boolean;
}) {
  const { message, state } = turn;
  return (
    <div className="turn">
      <div className="turn__q">{turn.question}</div>
      <div className="card card--pad">
        {state === "pending" && <ProgressBar label={progressLabel(message)} />}

        {(state === "error" || state === "timeout") && (
          <ErrorState
            title={state === "timeout" ? "Genie timed out" : "Genie couldn’t answer"}
            message={turn.error}
            onRetry={onRetry}
          />
        )}

        {state === "done" && message && (
          <div className="stack" style={{ gap: "var(--sp-4)" }}>
            {message.answer_text && (
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div
                  className="answer"
                  // Markdown is parsed then DOMPurify-sanitized before render.
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(message.answer_text) }}
                />
                <CopyButton text={message.answer_text} label="Copy Answer" />
              </div>
            )}

            <MessageResult message={message} />

            {message.status === "COMPLETED" && !message.is_empty && (
              <AnswerFeedback message={message} />
            )}

            {message.suggested_follow_ups.length > 0 && (
              <div>
                <div className="card__sub" style={{ marginBottom: "var(--sp-2)" }}>
                  Follow-up questions
                </div>
                <div className="row" style={{ gap: "var(--sp-2)" }}>
                  {message.suggested_follow_ups.map((q) => (
                    <button key={q} className="chip" disabled={busy} onClick={() => onFollowUp(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AskPage() {
  const { turns, busy, ask, retryLast, reset, conversationId } = useConversation();
  const [text, setText] = useState("");
  const [agent, setAgent] = useState<GenieAgent | null>(null);
  const [agentError, setAgentError] = useState<ApiError | null>(null);
  const agentMounted = useRef(true);
  const threadEnd = useRef<HTMLDivElement>(null);
  const questionInput = useRef<HTMLTextAreaElement>(null);

  const loadAgent = useCallback(async () => {
    setAgentError(null);
    try {
      const next = await api.genieAgent();
      if (agentMounted.current) setAgent(next);
    } catch (error) {
      if (agentMounted.current) {
        setAgentError(
          error instanceof ApiError
            ? error
            : new ApiError("Unable to load Genie Agent details.", 0),
        );
      }
    }
  }, []);

  useEffect(() => {
    agentMounted.current = true;
    void loadAgent();
    return () => {
      agentMounted.current = false;
    };
  }, [loadAgent]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns]);

  const submit = () => {
    const q = text.trim();
    if (!q || busy) return;
    ask(q);
    setText("");
  };

  const startNewConversation = () => {
    reset();
    setText("");
    window.requestAnimationFrame(() => questionInput.current?.focus());
  };

  if (agentError && isWakeableServiceError(agentError)) {
    return (
      <div className="stack">
        <div className="page-head">
          <h1>Ask ChicagoPulse</h1>
          <p>
            Ask about Chicago 311 requests, building permits, business licenses, and violations in
            plain English. Answers come from governed city data through Databricks Genie.
          </p>
        </div>
        <div className="card card--pad">
          <LiveServiceErrorState error={agentError} onRetry={loadAgent} />
        </div>
      </div>
    );
  }

  return (
    <div className="ask-workspace">
      <div className="page-head">
        <h1>Ask ChicagoPulse</h1>
        <p>
          Ask about Chicago 311 requests, building permits, business licenses, and violations in
          plain English. Answers come from governed city data through Databricks Genie.
        </p>
      </div>

      <GenieAgentHeader
        agent={agent}
        error={agentError?.message ?? null}
        conversationId={conversationId}
      />

      {turns.length === 0 ? (
        <div className="card card--pad">
          <SuggestedQuestions onPick={(q) => ask(q)} disabled={busy} />
        </div>
      ) : (
        <div className="ask-thread ask-thread--with-composer" aria-live="polite">
          {turns.map((t) => (
            <AnswerCard
              key={t.id}
              turn={t}
              busy={busy}
              onFollowUp={(q) => ask(q)}
              onRetry={retryLast}
            />
          ))}
          <div className="ask-thread__end" ref={threadEnd} />
        </div>
      )}

      <form
        className={`ask-composer ${turns.length > 0 ? "ask-composer--sticky" : ""}`}
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="visually-hidden" htmlFor="question">Your question</label>
        <textarea
          ref={questionInput}
          id="question"
          name="question"
          className="ask-composer__input"
          rows={3}
          maxLength={MAX_LEN}
          autoComplete="off"
          aria-describedby="question-help"
          placeholder="Ask about 311 requests, permits, licenses, or violations…"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <div className="ask-composer__actions">
          <span className="help" id="question-help">
            Enter to ask · Shift+Enter for a new line · {text.length}/{MAX_LEN}
          </span>
          <div className="row" style={{ gap: "var(--sp-2)" }}>
            {turns.length > 0 && (
              <button className="btn btn--sm" type="button" onClick={startNewConversation} disabled={busy}>
                <IconPlus size={15} /> New Conversation
              </button>
            )}
            <button className="btn btn--primary btn--sm" type="submit" disabled={busy || !text.trim()}>
              <IconSend size={15} /> {busy ? "Working…" : "Ask"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
