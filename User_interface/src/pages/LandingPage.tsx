import {
  ArrowRight,
  LogIn,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import { BrandLogo } from "@/components/brand";

export function LandingPage() {
  return (
    <main className="landing-page">
      <nav className="landing-nav" aria-label="Primary">
        <Link to="/" className="landing-brand">
          <BrandLogo />
        </Link>

        <div className="landing-nav__actions">
          <Link to="/login" className="landing-link-button">
            <LogIn size={18} aria-hidden="true" />
            <span>Login</span>
          </Link>

          <Link
            to="/register"
            className="landing-link-button landing-link-button--primary"
          >
            <UserPlus size={18} aria-hidden="true" />
            <span>Create Account</span>
          </Link>
        </div>
      </nav>

      <section className="landing-hero">
        <div className="landing-hero__content">
          <div className="landing-kicker">
            <ShieldCheck size={18} aria-hidden="true" />
            <span>Private conversations, built for daily use</span>
          </div>

          <h1>MYNA</h1>

          <p className="landing-hero__copy">
            A focused messenger workspace for conversations, contacts,
            and account control in one clean interface.
          </p>

          <div className="landing-hero__actions">
            <Link
              to="/login"
              className="landing-cta landing-cta--primary"
            >
              <LogIn size={20} aria-hidden="true" />
              <span>Open Login</span>
            </Link>

            <Link
              to="/register"
              className="landing-cta landing-cta--secondary"
            >
              <UserPlus size={20} aria-hidden="true" />
              <span>Create Account</span>
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        </div>

        <div className="landing-hero__media" aria-hidden="true">
          <BrandLogo className="landing-hero__brand-card" iconClassName="landing-hero__logo" />
        </div>
      </section>

      <section className="landing-features" aria-label="Highlights">
        <div className="landing-feature">
          <ShieldCheck size={22} aria-hidden="true" />
          <h2>Messaging</h2>
          <p>Jump straight into your conversation workspace after sign in.</p>
        </div>

        <div className="landing-feature">
          <Users size={22} aria-hidden="true" />
          <h2>Contacts</h2>
          <p>Manage saved contacts from the authenticated top bar.</p>
        </div>

        <div className="landing-feature">
          <ShieldCheck size={22} aria-hidden="true" />
          <h2>Account</h2>
          <p>Keep profile and session details visible where they matter.</p>
        </div>
      </section>
    </main>
  );
}
