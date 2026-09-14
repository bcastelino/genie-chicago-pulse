import DOMPurify from "dompurify";
import { marked } from "marked";

// Render Genie's Markdown answer to sanitized HTML. We never render raw
// model-generated HTML: Markdown is parsed, then DOMPurify strips anything
// unsafe (scripts, event handlers, iframes, etc.).
marked.setOptions({ gfm: true, breaks: true });

export function renderMarkdown(text: string): string {
  const rawHtml = marked.parse(text, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: [
      "p", "br", "strong", "em", "b", "i", "code", "pre",
      "ul", "ol", "li", "h1", "h2", "h3", "h4", "blockquote",
      "table", "thead", "tbody", "tr", "th", "td", "a",
    ],
    ALLOWED_ATTR: ["href", "title"],
    ALLOW_DATA_ATTR: false,
  });
}
