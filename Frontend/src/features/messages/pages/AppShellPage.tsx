import { useState } from "react";

import { useAuth } from "../../../app/providers/useAuth";
import { AppMainTabs, type AppTab } from "../components/AppMainTabs";
import { AppSidebar } from "../components/AppSidebar";

const ACTIVE_APP_TAB_STORAGE_KEY = "secure_chat_active_tab";

function readSavedAppTab(): AppTab {
  const savedTab = localStorage.getItem(ACTIVE_APP_TAB_STORAGE_KEY);

  if (
    savedTab === "home" ||
    savedTab === "contacts" ||
    savedTab === "profile" ||
    savedTab === "account-settings"
  ) {
    return savedTab;
  }

  return "home";
}

export function AppShellPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<AppTab>(readSavedAppTab);

  function changeActiveTab(tab: AppTab) {
    localStorage.setItem(ACTIVE_APP_TAB_STORAGE_KEY, tab);
    setActiveTab(tab);
  }

  return (
    <div className="logged-in-shell">
      <AppSidebar
        activeTab={activeTab}
        user={user}
        onOpenHome={() => changeActiveTab("home")}
        onOpenContacts={() => changeActiveTab("contacts")}
        onOpenProfile={() => changeActiveTab("profile")}
        onOpenAccountSettings={() => changeActiveTab("account-settings")}
      />

      <AppMainTabs activeTab={activeTab} onChangeTab={changeActiveTab} />
    </div>
  );
}