import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("renders basic markdown", () => {
    const html = renderMarkdown("Top **neighborhood** is Austin");
    expect(html).toContain("<strong>neighborhood</strong>");
  });

  it("strips scripts and event handlers", () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)"> <script>alert(2)</script> ok');
    expect(html.toLowerCase()).not.toContain("onerror");
    expect(html.toLowerCase()).not.toContain("<script");
    expect(html).toContain("ok");
  });

  it("drops disallowed tags like iframe", () => {
    const html = renderMarkdown('<iframe src="evil"></iframe>hello');
    expect(html.toLowerCase()).not.toContain("<iframe");
    expect(html).toContain("hello");
  });
});
