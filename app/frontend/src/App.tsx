import { Suspense, lazy, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { IconDatabase, IconMap, IconPulse, IconSearch } from "./components/icons";
import { Skeleton } from "./components/States";

const AskPage = lazy(() => import("./pages/AskPage").then((m) => ({ default: m.AskPage })));
const LandingPage = lazy(() =>
  import("./pages/LandingPage").then((m) => ({ default: m.LandingPage })),
);
const NeighborhoodPulsePage = lazy(() =>
  import("./pages/NeighborhoodPulsePage").then((m) => ({ default: m.NeighborhoodPulsePage })),
);
const DataHealthPage = lazy(() =>
  import("./pages/DataHealthPage").then((m) => ({ default: m.DataHealthPage })),
);

const NAV = [
  { to: "/ask", label: "Ask ChicagoPulse", short: "Ask", Icon: IconSearch },
  { to: "/neighborhoods", label: "Neighborhood Pulse", short: "Neighborhoods", Icon: IconMap },
  { to: "/data-health", label: "Data Health", short: "Data", Icon: IconDatabase },
];

function BrandMark() {
  // Four six-pointed stars motif from the Chicago flag, rendered minimally.
  return (
    <span className="brand__mark" aria-hidden="true">
      <IconPulse size={22} color="var(--chicago-sky)" />
    </span>
  );
}

export default function App() {
  const [mock, setMock] = useState(false);
  const { pathname } = useLocation();
  const isLanding = pathname === "/";
  const isMap = pathname === "/neighborhoods";

  useEffect(() => {
    api.health().then((h) => setMock(h.mock_mode)).catch(() => undefined);
  }, []);

  return (
    <div className={`app ${isLanding ? "app--landing" : ""}`}>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className={`topbar ${isLanding ? "topbar--landing" : ""}`}>
        <NavLink to="/" className="brand" aria-label="ChicagoPulse home">
          <BrandMark />
          <span className="brand__name" translate="no">
            Chicago<b>Pulse</b>
          </span>
        </NavLink>
        <nav className="mainnav" aria-label="Primary">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="topbar__actions">
          {mock && (
            <span className="topbar__env" title="Serving local mock data">
              Demo data
            </span>
          )}
        </div>
      </header>

      <main
        id="main"
        className={`content ${isLanding ? "content--landing" : ""} ${isMap ? "content--map" : ""}`}
      >
        <Suspense fallback={<Skeleton height={320} radius={10} />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/ask" element={<AskPage />} />
            <Route path="/neighborhoods" element={<NeighborhoodPulsePage />} />
            <Route path="/data-health" element={<DataHealthPage />} />
            <Route path="*" element={<Navigate to="/ask" replace />} />
          </Routes>
        </Suspense>
      </main>

      <footer className="app-footer">
        <div className="app-footer__inner">
          <div className="app-footer__identity">
            <span className="app-footer__name" translate="no">
              Chicago<b>Pulse</b>
            </span>
            <p>Neighborhood intelligence from governed City of Chicago open data.</p>
          </div>
          <nav className="app-footer__links" aria-label="Footer">
            <NavLink to="/data-health">Data health &amp; methodology</NavLink>
            <a href="https://data.cityofchicago.org/" target="_blank" rel="noreferrer">
              City of Chicago Data Portal
            </a>
          </nav>
        </div>
      </footer>

      <nav className="bottomnav" aria-label="Primary (mobile)">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} className="bottomnav__item">
            <n.Icon size={20} />
            <span>{n.short}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
