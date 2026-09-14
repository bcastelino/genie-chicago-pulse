import type { Provenance } from "../api/types";
import { IconChevron } from "./icons";

function provenanceRows(provenance: Provenance, dataSource?: string): [string, string | null][] {
  return [
    ["Data source", dataSource ?? "Databricks Genie \u00b7 governed Unity Catalog metrics"],
    ["Conversation ID", provenance.conversation_id],
    ["Message ID", provenance.message_id],
    ["Attachment ID", provenance.attachment_id],
    ["Statement ID", provenance.statement_id],
    ["Genie Space", provenance.space_id],
  ];
}

export function ProvenanceContent({
  provenance,
  dataSource,
}: {
  provenance: Provenance;
  dataSource?: string;
}) {
  const rows = provenanceRows(provenance, dataSource);
  return (
    <div className="provenance">
      <dl>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: "contents" }}>
            <dt>{label}</dt>
            <dd>{value ?? "\u2014"}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function ProvenanceDetails({
  provenance,
  dataSource,
}: {
  provenance: Provenance;
  dataSource?: string;
}) {
  return (
    <details className="disclosure">
      <summary>
        <span className="row" style={{ gap: 8 }}>
          <IconChevron size={16} />
          Data source &amp; request details
        </span>
      </summary>
      <div style={{ padding: "var(--sp-4)" }}>
        <ProvenanceContent provenance={provenance} dataSource={dataSource} />
      </div>
    </details>
  );
}
