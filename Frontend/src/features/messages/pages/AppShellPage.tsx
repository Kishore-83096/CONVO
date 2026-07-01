import { Link } from "react-router-dom";
import { MessengerWhoamiCard } from "../../messengerAuth/components/MessengerWhoamiCard";
import { useAuth } from "../../../app/providers/useAuth";
import { LogoutButton } from "../../auth/components/LogoutButton";

export function AppShellPage() {
  const { user } = useAuth();

  return (
    <main className="app-shell-page">
      <section className="app-shell-card">
        <div>
          <p className="eyebrow">Authenticated area</p>
          <h1>Myna App Shell</h1>
          <p>
            You are logged in. Messaging, contacts, E2EE device setup, and
            realtime features will be added in later phases.
          </p>
        </div>

        {user ? (
          <div className="session-card">
            <h2>Current session</h2>

            <dl className="auth-result-list">
              <div>
                <dt>Full name</dt>
                <dd>{user.fullName}</dd>
              </div>

              <div>
                <dt>Username</dt>
                <dd>{user.username}</dd>
              </div>

              <div>
                <dt>Email</dt>
                <dd>{user.email}</dd>
              </div>

              <div>
                <dt>Contact number</dt>
                <dd>{user.contactNumber}</dd>
              </div>
            </dl>
          </div>
        ) : null}
        <MessengerWhoamiCard />
        <div className="hero-actions">
          <Link className="button secondary" to="/settings">
            Open settings
          </Link>

          <LogoutButton />
        </div>
      </section>
    </main>
  );
}