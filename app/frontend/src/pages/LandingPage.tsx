import { Link } from "react-router-dom";
import { ChicagoHero } from "../components/ChicagoHero";
import { IconDatabase, IconMap, IconSearch } from "../components/icons";

const CHAPTERS = [
  {
    eyebrow: "Ask the city",
    title: "Start with the question you actually have.",
    body: "Ask about 311 requests, permits, licenses, and building violations in plain language. ChicagoPulse returns governed answers, charts, and the SQL behind them.",
    to: "/ask",
    action: "Ask a question",
    Icon: IconSearch,
  },
  {
    eyebrow: "Explore the neighborhoods",
    title: "See how one community area is moving.",
    body: "Read the latest completed month across Chicago’s 77 community areas, then compare local conditions and twelve-month trends without leaving the map.",
    to: "/neighborhoods",
    action: "Open Neighborhood Pulse",
    Icon: IconMap,
  },
  {
    eyebrow: "Trust the refresh",
    title: "Know when the data truly finished.",
    body: "Freshness is backed by successful pipeline run state, with source coverage and ingestion details available when you need to verify an answer.",
    to: "/data-health",
    action: "View Data Health",
    Icon: IconDatabase,
  },
] as const;

export function LandingPage() {
  return (
    <div className="landing">
      <ChicagoHero />

      <section className="landing-story" aria-labelledby="landing-story-title">
        <div className="landing-story__intro">
          <span className="overline">A clearer view of Chicago</span>
          <h2 id="landing-story-title">From a citywide signal to the block-level question behind it.</h2>
          <p>
            ChicagoPulse connects neighborhood conditions, governed city data, and plain-language
            questions in one place built for residents and community groups.
          </p>
        </div>

        <div className="landing-story__chapters">
          {CHAPTERS.map(({ eyebrow, title, body, to, action, Icon }) => (
            <article className="landing-chapter" key={to}>
              <div className="landing-chapter__icon" aria-hidden="true">
                <Icon size={22} />
              </div>
              <div>
                <span className="overline">{eyebrow}</span>
                <h3>{title}</h3>
                <p>{body}</p>
                <Link to={to} className="text-link">
                  {action} <span aria-hidden="true">→</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-close" aria-labelledby="landing-close-title">
        <span className="overline">Chicago at a glance</span>
        <h2 id="landing-close-title">The city is already speaking.</h2>
        <p>Ask the next question, or begin with the neighborhood you know best.</p>
        <div className="landing-close__actions">
          <Link className="hero__cta hero__cta--light" to="/ask">
            Ask ChicagoPulse <span aria-hidden="true">→</span>
          </Link>
          <Link className="hero__cta hero__cta--ghost" to="/neighborhoods">
            Explore neighborhoods
          </Link>
        </div>
      </section>
    </div>
  );
}
