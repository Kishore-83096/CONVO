import { Link } from "react-router-dom";

import { LogoutButton } from "../../auth/components/LogoutButton";
import { AccountSettingsPanel } from "../components/AccountSettingsPanel";

export function SettingsPage() {
  return (
    <main className="standalone-settings-page">
      <section className="standalone-settings-panel">
        <AccountSettingsPanel />

        <div className="hero-actions">
          <Link className="button ghost" to="/app">
            Back to app
          </Link>

          <LogoutButton />
        </div>
      </section>
    </main>
  );
}
