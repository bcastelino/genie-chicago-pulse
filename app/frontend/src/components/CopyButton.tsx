import { useState } from "react";
import { IconCheck, IconCopy } from "./icons";

export function CopyButton({
  text,
  label = "Copy",
  className = "btn btn--sm btn--ghost",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      className={className}
      onClick={onCopy}
      aria-label={copied ? `${label}: copied` : label}
    >
      {copied ? <IconCheck size={15} /> : <IconCopy size={15} />}
      <span>{copied ? "Copied" : label}</span>
    </button>
  );
}
