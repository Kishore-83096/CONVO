import type { AuthSession } from "@/app/parrot_identity/auth/auth-session"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"

interface ProfileMenuProps {
  activeMainView: "empty" | "chat" | "profile" | "account" | "appearance" | "contact"
  currentTheme: string
  isLoggingOut: boolean
  isProfileLoading: boolean
  logoutError: string
  profile: CompleteProfile | null
  profileError: string
  session: AuthSession
  onOpenAppearance: () => void
  onOpenAccount: () => void
  onOpenProfile: () => void
  onLogout: () => void
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
}

function ProfileMenu({
  activeMainView,
  currentTheme,
  isLoggingOut,
  isProfileLoading,
  logoutError,
  profile,
  profileError,
  session,
  onOpenAppearance,
  onOpenAccount,
  onOpenProfile,
  onLogout,
}: ProfileMenuProps) {
  const profileIdentity = profile?.identity ?? null
  const profilePicture = profile?.profile_picture ?? null
  const displayName = profileIdentity?.full_name ?? session.user.full_name
  const displayEmail = profileIdentity?.email ?? session.user.email
  const displayUsername = profileIdentity?.username

  return (
    <section className="sidebar-view active" aria-label="Profile menu tab">
      <div className="profile-area">
        {profilePicture ? (
          <img className="profile-avatar" src={profilePicture.url} alt="" />
        ) : (
          <span className="profile-avatar">{initials(displayName)}</span>
        )}
        <span className="profile-summary-copy">
          <strong>{displayName}</strong>
          <span>{displayEmail}</span>
          <small>
            {isProfileLoading
              ? "LOADING PROFILE"
              : displayUsername
                ? `@${displayUsername}`
                : "USERNAME UNAVAILABLE"}
          </small>
        </span>
      </div>

      {profileError ? (
        <p className="contact-error" role="alert">
          {profileError}
        </p>
      ) : null}

      <button
        className={`profile-menu-button ${
          activeMainView === "profile" ? "active" : ""
        }`}
        type="button"
        onClick={onOpenProfile}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21C4 16.6 7.6 13 12 13C16.4 13 20 16.6 20 21" />
        </svg>
        <span>Profile</span>
      </button>

      <button
        className={`profile-menu-button ${
          activeMainView === "account" ? "active" : ""
        }`}
        type="button"
        onClick={onOpenAccount}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 6H20" />
          <path d="M4 12H20" />
          <path d="M4 18H20" />
          <circle cx="9" cy="6" r="2" />
          <circle cx="15" cy="12" r="2" />
          <circle cx="10" cy="18" r="2" />
        </svg>
        <span>Account Settings</span>
      </button>

      <button
        className={`profile-menu-button ${
          activeMainView === "appearance" ? "active" : ""
        }`}
        type="button"
        aria-label={`Open appearance settings. Current theme: ${currentTheme}`}
        onClick={onOpenAppearance}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <circle cx="9" cy="10" r="1" />
          <circle cx="13" cy="8" r="1" />
          <circle cx="15" cy="13" r="1" />
          <path d="M11 16H12" />
        </svg>
        <span>Appearance</span>
      </button>

      <button
        className="profile-menu-button logout-button"
        type="button"
        disabled={isLoggingOut}
        onClick={onLogout}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M10 4H5V20H10" />
          <path d="M14 8L18 12L14 16" />
          <path d="M18 12H9" />
        </svg>
        <span>{isLoggingOut ? "Logging out..." : "Logout"}</span>
      </button>

      {logoutError ? (
        <p className="contact-error" role="alert">
          {logoutError}
        </p>
      ) : null}
    </section>
  )
}

export default ProfileMenu
