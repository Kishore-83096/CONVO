import { ContactsPanel } from "../../contacts/components/ContactsPanel";
import { MyProfilePanel } from "../../profiles/components/MyProfilePanel";
import { AccountSettingsPanel } from "../../settings/components/AccountSettingsPanel";

export type AppTab = "home" | "contacts" | "profile" | "account-settings";

type AppMainTabsProps = {
  activeTab: AppTab;
  onChangeTab: (tab: AppTab) => void;
};

export function AppMainTabs({ activeTab, onChangeTab }: AppMainTabsProps) {
  return (
    <main className="app-main">
      <section
        className={`main-view motion-tab-panel ${
          activeTab === "home" ? "active" : ""
        }`}
        aria-label="Secure Chat"
      >
        <header className="conversation-header secure-chat-header">
          <div className="conversation-title">
            <img
              alt=""
              aria-hidden="true"
              className="conversation-avatar secure-chat-header-icon"
              src="/secure-chat-icon.png"
            />
            <div>
              <strong>Secure Chat</strong>
              <span>Ready</span>
            </div>
          </div>

          <div className="header-action-row">
            <button
              aria-label="Open contacts"
              className="header-icon-button motion-button-switch motion-spin-button"
              onClick={() => onChangeTab("contacts")}
              type="button"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M16 11A4 4 0 1 0 16 3A4 4 0 0 0 16 11Z" />
                <path d="M2 21A7 7 0 0 1 16 21" />
                <path d="M19 14V20" />
                <path d="M16 17H22" />
              </svg>
            </button>

            <button
              aria-label="Open profile"
              className="header-icon-button motion-button-switch motion-spin-button"
              onClick={() => onChangeTab("profile")}
              type="button"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 12A4 4 0 1 0 12 4A4 4 0 0 0 12 12Z" />
                <path d="M4 21A8 8 0 0 1 20 21" />
              </svg>
            </button>
          </div>
        </header>

        <div className="empty-main-content">
          <img
            alt=""
            aria-hidden="true"
            className="empty-main-icon"
            src="/secure-chat-icon.png"
          />
          <h1>Secure Chat</h1>
        </div>
      </section>

      <section
        className={`main-view workspace-view motion-tab-panel ${
          activeTab === "contacts" ? "active" : ""
        }`}
        aria-label="Contacts"
      >
        <header className="workspace-header">
          <div className="workspace-title-row">
            <div>
              <span className="section-kicker">Contacts</span>
              <h2>Contact APIs</h2>
            </div>

            <button
              aria-label="Close contacts"
              className="header-icon-button motion-button-switch"
              onClick={() => onChangeTab("home")}
              type="button"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 6L6 18" />
                <path d="M6 6L18 18" />
              </svg>
            </button>
          </div>
        </header>

        <div className="workspace-content">
          <ContactsPanel />
        </div>
      </section>

      <section
        className={`main-view workspace-view motion-tab-panel ${
          activeTab === "profile" ? "active" : ""
        }`}
        aria-label="My profile"
      >
        <header className="workspace-header">
          <div className="workspace-title-row">
            <div>
              <span className="section-kicker">Profile</span>
              <h2>My Profile</h2>
            </div>

            <button
              aria-label="Close profile"
              className="header-icon-button motion-button-switch"
              onClick={() => onChangeTab("home")}
              type="button"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 6L6 18" />
                <path d="M6 6L18 18" />
              </svg>
            </button>
          </div>
        </header>

        <div className="workspace-content">
          <MyProfilePanel />
        </div>
      </section>

      <section
        className={`main-view workspace-view motion-tab-panel ${
          activeTab === "account-settings" ? "active" : ""
        }`}
        aria-label="Account settings"
      >
        <header className="workspace-header">
          <div className="workspace-title-row">
            <div>
              <span className="section-kicker">Account</span>
              <h2>Settings</h2>
            </div>

            <button
              aria-label="Close account settings"
              className="header-icon-button motion-button-switch"
              onClick={() => onChangeTab("home")}
              type="button"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 6L6 18" />
                <path d="M6 6L18 18" />
              </svg>
            </button>
          </div>
        </header>

        <div className="workspace-content">
          <AccountSettingsPanel compact />
        </div>
      </section>
    </main>
  );
}