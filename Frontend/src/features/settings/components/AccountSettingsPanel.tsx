import { useState } from "react";

import { DeleteAccountPanel } from "./DeleteAccountPanel";
import { ResetPasswordPanel } from "./ResetPasswordPanel";

type SettingsTab = "reset-password" | "delete-account";

type AccountSettingsPanelProps = {
  compact?: boolean;
};

export function AccountSettingsPanel({
  compact = false,
}: AccountSettingsPanelProps) {
  const [settingsTab, setSettingsTab] =
    useState<SettingsTab>("reset-password");

  return (
    <section className="account-settings-panel">
      {!compact ? (
        <div className="section-heading">
          <p className="eyebrow">Account settings</p>
          <h1>Account Settings</h1>
          <p>
            Manage sensitive Identity actions from inside the app. You must
            type your account details manually for each action.
          </p>
        </div>
      ) : null}

      <div
        className="workspace-tabs"
        role="tablist"
        aria-label="Account settings"
      >
        <button
          aria-selected={settingsTab === "reset-password"}
          className={`workspace-tab motion-button-switch ${
            settingsTab === "reset-password" ? "active" : ""
          }`}
          onClick={() => setSettingsTab("reset-password")}
          role="tab"
          type="button"
        >
          Reset Password
        </button>

        <button
          aria-selected={settingsTab === "delete-account"}
          className={`workspace-tab motion-button-switch ${
            settingsTab === "delete-account" ? "active" : ""
          }`}
          onClick={() => setSettingsTab("delete-account")}
          role="tab"
          type="button"
        >
          Delete Account
        </button>
      </div>

      <div className="settings-tab-panels">
        <div
          className={`settings-tab-panel motion-tab-panel ${
            settingsTab === "reset-password" ? "active" : ""
          }`}
        >
          <ResetPasswordPanel />
        </div>

        <div
          className={`settings-tab-panel motion-tab-panel ${
            settingsTab === "delete-account" ? "active" : ""
          }`}
        >
          <DeleteAccountPanel />
        </div>
      </div>
    </section>
  );
}
