// Starter questions — drawn from the repo's verified Genie benchmark suite
// (genie/benchmark_catalog.md) so they are known to return good results.
export const SUGGESTED_QUESTIONS: string[] = [
  "Which 10 Chicago neighborhoods had the most 311 requests in the latest completed month?",
  "Which neighborhoods had the largest month-over-month increase in 311 requests?",
  "Show Chicago\u2019s total monthly 311 request volume for the past 12 months.",
  "Compare 311 requests, building violations, permits, and business licenses for Austin, Lake View, West Town, and Lincoln Park.",
  "Which neighborhoods had at least 3,000 311 requests and at least 100 building violations last month?",
  "What were the 15 most common 311 service request types across Chicago last month?",
];

export function SuggestedQuestions({
  onPick,
  disabled,
}: {
  onPick: (q: string) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <div className="card__sub" style={{ marginBottom: "var(--sp-3)" }}>
        Try one of these
      </div>
      <div className="row" style={{ gap: "var(--sp-2)" }}>
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="chip"
            disabled={disabled}
            onClick={() => onPick(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
