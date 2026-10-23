import { useEffect, useState } from "react";

import AccuracyScreen from "./AccuracyScreen";
import ForecastScreen from "./ForecastScreen";
import type { Theme } from "./ui";

type Tab = "forecast" | "accuracy";

const initialTab: Tab =
  new URLSearchParams(window.location.search).get("screen") === "accuracy"
    ? "accuracy"
    : "forecast";

function initialTheme(): Theme {
  const stored = window.localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function MoonIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  const toggleSidebar = () => setSidebarOpen((value) => !value);
  const toggleTheme = () =>
    setTheme((value) => (value === "dark" ? "light" : "dark"));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("theme", theme);
  }, [theme]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <button
            type="button"
            className="sidebar-toggle"
            onClick={toggleSidebar}
            aria-label="Toggle controls"
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? "⟨" : "⟩"}
          </button>
          <div className="brand">
            <span className="brand-mark">W</span>
            <div className="brand-copy">
              <h1>Wind Forecast</h1>
              <p className="brand-sub">
                Elexon national wind · January 2026 · UTC
              </p>
            </div>
          </div>
        </div>
        <div className="header-right">
          <nav className="tabs" aria-label="Screens">
            <button
              type="button"
              className={tab === "forecast" ? "active" : ""}
              onClick={() => setTab("forecast")}
            >
              See Forecast
            </button>
            <button
              type="button"
              className={tab === "accuracy" ? "active" : ""}
              onClick={() => setTab("accuracy")}
            >
              Review Forecasts
            </button>
          </nav>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={
              theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            }
            aria-pressed={theme === "dark"}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
        </div>
      </header>

      <div className="app-body">
        {tab === "forecast" ? (
          <ForecastScreen
            sidebarOpen={sidebarOpen}
            onToggleSidebar={toggleSidebar}
            theme={theme}
          />
        ) : (
          <AccuracyScreen
            sidebarOpen={sidebarOpen}
            onToggleSidebar={toggleSidebar}
            theme={theme}
          />
        )}
      </div>
    </div>
  );
}
