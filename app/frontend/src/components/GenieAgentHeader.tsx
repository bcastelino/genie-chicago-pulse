import type { GenieAgent } from "../api/types";
import { formatDateTime } from "../lib/format";
import { renderMarkdown } from "../lib/markdown";
import { IconAgent, IconChevron, IconExternalLink } from "./icons";

export function GenieAgentHeader({
  agent,
  error,
  conversationId,
}: {
  agent: GenieAgent | null;
  error: string | null;
  conversationId: string | null;
}) {
  const title = agent?.title || "ChicagoPulse Genie";
  const conversationUrl = agent?.space_url && conversationId
    ? `${agent.space_url}/chats/${encodeURIComponent(conversationId)}`
    : null;

  return (
    <section className="agent-profile" aria-labelledby="genie-agent-title">
      <div className="agent-profile__main">
        <div className="agent-profile__mark" aria-hidden="true">
          <IconAgent size={22} />
        </div>
        <div className="agent-profile__identity">
          <div className="agent-profile__title-row">
            <h2 id="genie-agent-title">{title}</h2>
            <span className="badge badge--ok">
              <span className="badge__dot" /> Governed data
            </span>
          </div>
          <p>Databricks Genie Agent · Chicago community-area intelligence</p>
        </div>
        <div className="agent-profile__links">
          {agent?.space_url && (
            <a className="btn btn--sm" href={agent.space_url} target="_blank" rel="noreferrer">
              Open in Genie <IconExternalLink size={14} />
            </a>
          )}
          {conversationUrl && (
            <a className="btn btn--sm btn--ghost" href={conversationUrl} target="_blank" rel="noreferrer">
              View conversation <IconExternalLink size={14} />
            </a>
          )}
        </div>
      </div>

      {error && (
        <p className="agent-profile__notice" role="status">
          Agent details are temporarily unavailable. You can still ask questions.
        </p>
      )}

      {agent && (
        <details className="agent-profile__details">
          <summary>
            <span>
              <IconChevron size={15} /> Capabilities, limits, and technical details
            </span>
          </summary>
          <div className="agent-profile__detail-grid">
            <div
              className="agent-profile__description"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(agent.description) }}
            />
            <dl>
              <div>
                <dt>Last updated</dt>
                <dd>{agent.updated_at ? formatDateTime(agent.updated_at) : "—"}</dd>
              </div>
              <div>
                <dt>Space ID</dt>
                <dd>{agent.space_id}</dd>
              </div>
              <div>
                <dt>Warehouse</dt>
                <dd>{agent.warehouse_id ?? "—"}</dd>
              </div>
            </dl>
          </div>
        </details>
      )}
    </section>
  );
}
