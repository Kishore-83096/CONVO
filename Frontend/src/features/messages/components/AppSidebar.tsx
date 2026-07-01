import { useEffect, useRef, useState } from "react";

import { ThemeToggle } from "../../../shared/ui/ThemeToggle";
import type { AppTab } from "./AppMainTabs";
import type { ApiResult } from "../../../shared/api/responseEnvelope";
import type { StoredCurrentUser } from "../../../shared/storage/db";
import { LogoutButton } from "../../auth/components/LogoutButton";
import { getMessengerWhoami } from "../../messengerAuth/api";
import type { MessengerWhoamiResponse } from "../../messengerAuth/types";
import { useMyProfilePicture } from "../../profiles/hooks";
import type { ProfilePicture } from "../../profiles/types";

type AppSidebarProps = {
  user: StoredCurrentUser | null;
  activeTab: AppTab;
  onOpenHome: () => void;
  onOpenContacts: () => void;
  onOpenProfile: () => void;
  onOpenAccountSettings: () => void;
};

type FlexibleProfilePicture = ProfilePicture & {
  url?: string | null;
  picture_url?: string | null;
  profile_picture_url?: string | null;
  cloudinary_url?: string | null;
  file_url?: string | null;
  image?: string | null;
};

function getInitials(user: StoredCurrentUser | null): string {
  if (!user) {
    return "--";
  }

  const name = user.fullName || user.username;
  return name
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function getProfilePictureUrl(
  picture: FlexibleProfilePicture | null | undefined,
) {
  return (
    picture?.secure_url ||
    picture?.image_url ||
    picture?.url ||
    picture?.picture_url ||
    picture?.profile_picture_url ||
    picture?.cloudinary_url ||
    picture?.file_url ||
    picture?.image ||
    ""
  );
}

function createMessengerTimeoutResult(): ApiResult<MessengerWhoamiResponse> {
  return {
    ok: false,
    status: 0,
    message: "Messenger connection timed out.",
  };
}

export function AppSidebar({
  user,
  activeTab,
  onOpenHome,
  onOpenContacts,
  onOpenProfile,
  onOpenAccountSettings,
}: AppSidebarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(() => activeTab !== "home");
  const [isMenuClosing, setIsMenuClosing] = useState(false);
  const [messengerStatus, setMessengerStatus] = useState<
    "idle" | "checking" | "connected" | "failed"
  >("idle");
  const messengerRequestId = useRef(0);
  const profilePictureQuery = useMyProfilePicture(Boolean(user));
  const profilePicture = profilePictureQuery.data?.ok
    ? (profilePictureQuery.data.data as FlexibleProfilePicture | null)
    : undefined;
  const profilePictureUrl = getProfilePictureUrl(profilePicture);

  useEffect(() => {
    if (!user) {
      return;
    }

    const requestId = messengerRequestId.current + 1;
    messengerRequestId.current = requestId;

    window.queueMicrotask(() => {
      if (messengerRequestId.current !== requestId) {
        return;
      }

      setMessengerStatus("checking");
    });

    const timeout = new Promise<ApiResult<MessengerWhoamiResponse>>(
      (resolve) => {
        window.setTimeout(() => resolve(createMessengerTimeoutResult()), 20000);
      },
    );

    void Promise.race([getMessengerWhoami(), timeout])
      .then((nextResult) => {
        if (messengerRequestId.current !== requestId) {
          return;
        }

        setMessengerStatus(nextResult.ok ? "connected" : "failed");
      })
      .catch(() => {
        if (messengerRequestId.current !== requestId) {
          return;
        }

        setMessengerStatus("failed");
      });
  }, [user]);

  const statusClass =
    messengerStatus === "connected"
      ? "status-dot--ok"
      : messengerStatus === "failed"
        ? "status-dot--error"
        : "";

  const statusText =
    messengerStatus === "checking"
      ? "Messenger checking"
      : messengerStatus === "connected"
        ? "Messenger connected"
        : messengerStatus === "failed"
          ? "Messenger unavailable"
          : "Messenger not checked";

  useEffect(() => {
    if (activeTab === "home") {
      return;
    }

    window.queueMicrotask(() => {
      setIsMenuClosing(false);
      setIsMenuOpen(true);
    });
  }, [activeTab]);

  function handleToggleMenu() {
    if (isMenuOpen) {
      setIsMenuClosing(true);
      window.setTimeout(() => {
        setIsMenuOpen(false);
        setIsMenuClosing(false);
      }, 170);
      return;
    }

    setIsMenuOpen(true);
  }

  return (
    <aside className="app-sidebar">
      <header className="app-sidebar__top">
        <button
          className="brand-lockup app-brand-button"
          onClick={onOpenHome}
          type="button"
        >
          <img
            alt=""
            aria-hidden="true"
            className="brand-icon"
            src="/secure-chat-icon.png"
          />
          <span className="brand-name">Secure Chat</span>
        </button>

        <button
          aria-expanded={isMenuOpen}
          aria-label={isMenuOpen ? "Close account menu" : "Open account menu"}
          className={`header-icon-button motion-button-switch ${
            isMenuOpen ? "active" : ""
          }`}
          onClick={handleToggleMenu}
          type="button"
        >
          {isMenuOpen ? (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 6L6 18" />
              <path d="M6 6L18 18" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 7H20" />
              <path d="M4 12H20" />
              <path d="M4 17H20" />
            </svg>
          )}
        </button>
      </header>

      <div className="sidebar-body">
        <section className="sidebar-view active" aria-label="Secure Chat home">
          {!isMenuOpen ? (
            <div className="motion-sidebar-view motion-tab-panel active">
              <div className="sidebar-view-heading contact-title-row">
                <h2>Contact</h2>
                <button
                  aria-label="Open contacts"
                  className="header-icon-button motion-button-switch motion-spin-button"
                  onClick={onOpenContacts}
                  type="button"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M16 11A4 4 0 1 0 16 3A4 4 0 0 0 16 11Z" />
                    <path d="M2 21A7 7 0 0 1 16 21" />
                    <path d="M19 14V20" />
                    <path d="M16 17H22" />
                  </svg>
                </button>
              </div>

              <p className="sidebar-empty-note">
                Open Contacts to search, save, and inspect contact details.
              </p>
            </div>
          ) : (
            <div
              className={`motion-sidebar-view motion-tab-panel active ${
                isMenuClosing ? "is-closing" : ""
              }`}
            >
              <div className="profile-area">
                {profilePictureUrl ? (
                  <img
                    alt="Current profile"
                    className="profile-avatar profile-avatar--image"
                    src={profilePictureUrl}
                  />
                ) : (
                  <span className="profile-avatar">{getInitials(user)}</span>
                )}
              </div>

              <dl className="profile-detail-list">
                <div>
                  <dt>Full name</dt>
                  <dd>{user?.fullName ?? "Signed in"}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{user?.email ?? "Session loading"}</dd>
                </div>
                <div>
                  <dt>Contact number</dt>
                  <dd>{user?.contactNumber ?? "Session loading"}</dd>
                </div>
                <div>
                  <dt>Username</dt>
                  <dd>{user?.username ?? "Session loading"}</dd>
                </div>
              </dl>

              <LogoutButton fullWidth />

              <div className="connection-panel">
                <div className="messenger-status-line">
                  <span className={`status-dot ${statusClass}`} />
                  <strong>{statusText}</strong>
                </div>
              </div>

              <nav className="profile-menu-list" aria-label="Account actions">
                <button
                  className={`profile-menu-button ${
                    activeTab === "contacts" ? "active" : ""
                  } motion-button-switch motion-spin-button`}
                  onClick={onOpenContacts}
                  type="button"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M16 11A4 4 0 1 0 16 3A4 4 0 0 0 16 11Z" />
                    <path d="M2 21A7 7 0 0 1 16 21" />
                    <path d="M19 14V20" />
                    <path d="M16 17H22" />
                  </svg>
                  <span>Contacts</span>
                </button>

                <button
                  className={`profile-menu-button ${
                    activeTab === "profile" ? "active" : ""
                  } motion-button-switch motion-spin-button`}
                  onClick={onOpenProfile}
                  type="button"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 12A4 4 0 1 0 12 4A4 4 0 0 0 12 12Z" />
                    <path d="M4 21A8 8 0 0 1 20 21" />
                  </svg>
                  <span>My Profile</span>
                </button>

                <button
                  className={`profile-menu-button ${
                    activeTab === "account-settings" ? "active" : ""
                  } motion-button-switch motion-spin-button`}
                  onClick={onOpenAccountSettings}
                  type="button"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 15.5A3.5 3.5 0 1 0 12 8.5A3.5 3.5 0 0 0 12 15.5Z" />
                    <path d="M19 12A7 7 0 0 0 18.9 10.8L21 9.2L19 5.8L16.5 6.8A7.5 7.5 0 0 0 14.5 5.6L14.2 3H9.8L9.5 5.6A7.5 7.5 0 0 0 7.5 6.8L5 5.8L3 9.2L5.1 10.8A7 7 0 0 0 5.1 13.2L3 14.8L5 18.2L7.5 17.2A7.5 7.5 0 0 0 9.5 18.4L9.8 21H14.2L14.5 18.4A7.5 7.5 0 0 0 16.5 17.2L19 18.2L21 14.8L18.9 13.2A7 7 0 0 0 19 12Z" />
                  </svg>
                  <span>Account Settings</span>
                </button>

                <div className="profile-menu-button theme-menu-row">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 3A9 9 0 1 0 21 12C21 7.03 16.97 3 12 3Z" />
                    <path d="M12 3V21" />
                  </svg>
                  <ThemeToggle />
                </div>
              </nav>
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}