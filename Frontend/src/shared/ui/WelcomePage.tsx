import { Link } from "react-router-dom";

import { useAuth } from "../../app/providers/useAuth";
import { PublicLayout } from "./PublicLayout";

const features = [
  ["Authentication", "Registration and login flows will establish secure user identity before private app routes unlock."],
  ["Contacts", "Search, save, preview, and manage trusted people before messages begin moving."],
  ["Encrypted messaging", "The messenger surface is being prepared for private direct conversations and encrypted payloads."],
  ["Groups", "Shared rooms, membership controls, and group security panels are planned into the flow."],
  ["Attachments", "Files and media will travel through dedicated attachment picking, preview, and transfer steps."],
  ["Realtime", "Delivery events, receipts, typing signals, and presence are part of the realtime foundation."],
];

const flowSteps = [
  "Register",
  "Login",
  "Device setup",
  "Contacts",
  "Messaging",
  "Realtime",
];

export function WelcomePage() {
  const { user, isBootstrapping } = useAuth();

  return (
    <PublicLayout>
      <section className="hero-section">
        <div className="hero-content">
          <p className="eyebrow">Sprint 0 frontend foundation</p>
          <h1>Private messaging, assembled phase by phase.</h1>
          <p className="hero-description">
            This frontend is being built in careful layers for authentication,
            contacts, encrypted messaging, groups, attachments, realtime
            delivery, receipts, and presence.
          </p>

          <div className="hero-actions">
            <Link className="button" to="/register">
              Create account
            </Link>
            <Link className="button secondary" to="/login">
              Login
            </Link>
          </div>

          <div className="session-strip">
            {isBootstrapping
              ? "Checking local secure storage..."
              : user
                ? `Session found for ${user.username}`
                : "No active session yet. Login will be added in Sprint 1."}
          </div>
        </div>

        <div aria-label="Messenger interface preview" className="hero-panel">
          <div className="mock-window">
            <div className="mock-window__top">
              <span />
              <span />
              <span />
            </div>
            <div className="mock-chat">
              <aside className="mock-sidebar">
                <span />
                <span />
                <span />
              </aside>
              <div className="mock-main">
                <div className="mock-message">Device keys ready</div>
                <div className="mock-message mock-message--sent">
                  Encrypted draft queued
                </div>
                <div className="mock-message">Receipt pending</div>
                <div className="mock-composer" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="public-section" id="features">
        <div className="section-heading">
          <p className="eyebrow">Core modules</p>
          <h2>Feature surface</h2>
        </div>
        <div className="feature-grid">
          {features.map(([title, description]) => (
            <article className="feature-card" key={title}>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="public-section split-section" id="security">
        <div className="section-heading">
          <p className="eyebrow">Storage policy</p>
          <h2>Security rules stay visible.</h2>
        </div>
        <ul className="security-list">
          <li>No sensitive values are stored in localStorage.</li>
          <li>IndexedDB remains the secure storage foundation.</li>
          <li>Only the non-sensitive theme preference is remembered locally.</li>
          <li>Policy-aware UI will support block and ghost rules.</li>
        </ul>
      </section>

      <section className="public-section" id="flow">
        <div className="section-heading">
          <p className="eyebrow">Application path</p>
          <h2>From account creation to realtime presence.</h2>
        </div>
        <div className="flow-grid">
          {flowSteps.map((step, index) => (
            <div className="feature-card" key={step}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <h3>{step}</h3>
            </div>
          ))}
        </div>
      </section>

      <section className="public-section diagnostics-section" id="health">
        <div className="section-heading">
          <p className="eyebrow">Diagnostics</p>
          <h2>Health checks remain public.</h2>
        </div>
        <div className="hero-actions">
          <Link className="button" to="/health/identity">
            Identity Health
          </Link>
          <Link className="button secondary" to="/health/messenger">
            Messenger Health
          </Link>
        </div>
      </section>

      <footer className="public-footer">
        <div>
          <strong>Phase 0.11</strong>
          <span>Public shell, theme memory, and diagnostics foundation.</span>
        </div>
        <div className="public-footer__links">
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
          <Link to="/health/identity">Identity health</Link>
          <Link to="/health/messenger">Messenger health</Link>
        </div>
      </footer>
    </PublicLayout>
  );
}
