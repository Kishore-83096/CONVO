import { KeyRound, LogOut, Palette, SlidersHorizontal, UserRound } from "lucide-react"

import type { AuthSession } from "@/app/identity/auth/auth-session"
import type { CompleteProfile } from "@/app/workspace/profile/profile.types"

interface ProfileMenuProps {
  activeMainView:
    | "empty"
    | "chat"
    | "profile"
    | "account"
    | "appearance"
    | "contact"
    | "device"
  currentTheme: string
  isLoggingOut: boolean
  isProfileLoading: boolean
  logoutError: string
  profile: CompleteProfile | null
  profileError: string
  session: AuthSession
  onOpenAppearance: () => void
  onOpenAccount: () => void
  onOpenDevice: () => void
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
  onOpenDevice,
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
        <UserRound aria-hidden="true" />
        <span>Profile</span>
      </button>

      <button
        className={`profile-menu-button ${
          activeMainView === "account" ? "active" : ""
        }`}
        type="button"
        onClick={onOpenAccount}
      >
        <SlidersHorizontal aria-hidden="true" />
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
        <Palette aria-hidden="true" />
        <span>Appearance</span>
      </button>

      <button
        className={`profile-menu-button ${
          activeMainView === "device" ? "active" : ""
        }`}
        type="button"
        onClick={onOpenDevice}
      >
        <KeyRound aria-hidden="true" />
        <span>E2EE Device</span>
      </button>

      <button
        className="profile-menu-button logout-button"
        type="button"
        disabled={isLoggingOut}
        onClick={onLogout}
      >
        <LogOut aria-hidden="true" />
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
