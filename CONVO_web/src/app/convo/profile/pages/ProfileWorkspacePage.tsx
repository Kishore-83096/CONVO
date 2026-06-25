import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import { getProfile } from "@/app/convo/profile/profile.api"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"
import AddressProfilePage from "@/app/convo/profile/pages/AddressProfilePage"
import EventsProfilePage from "@/app/convo/profile/pages/EventsProfilePage"
import ProfilePage from "@/app/convo/profile/pages/ProfilePage"
import ProfilePicturePage from "@/app/convo/profile/pages/ProfilePicturePage"
import UpdateProfilePage from "@/app/convo/profile/pages/UpdateProfilePage"
import { clearAuthSession } from "@/app/parrot_identity/auth/auth-session"

interface ProfileWorkspacePageProps {
  accessToken: string
  initialProfile: CompleteProfile | null
  onClose: () => void
  onProfileLoaded: (profile: CompleteProfile | null) => void
  storageKey: string
}

type ProfileTab = "overview" | "basic" | "address" | "events" | "picture"

const profileTabs: { id: ProfileTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "basic", label: "Basic" },
  { id: "address", label: "Address" },
  { id: "events", label: "Events" },
  { id: "picture", label: "Picture" },
]

function savedProfileTab(storageKey: string): ProfileTab {
  const tab = localStorage.getItem(storageKey)
  const validTabs = profileTabs.map((profileTab) => profileTab.id)

  return validTabs.includes(tab as ProfileTab)
    ? (tab as ProfileTab)
    : "overview"
}

function ProfileWorkspacePage({
  accessToken,
  initialProfile,
  onClose,
  onProfileLoaded,
  storageKey,
}: ProfileWorkspacePageProps) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<ProfileTab>(() =>
    savedProfileTab(storageKey),
  )
  const [profile, setProfile] = useState<CompleteProfile | null>(initialProfile)
  const [isLoading, setIsLoading] = useState(!initialProfile)
  const [error, setError] = useState("")

  const loadProfile = useCallback(async () => {
    setIsLoading(true)
    setError("")

    try {
      const response = await getProfile(accessToken)
      const nextProfile = response.data ?? null
      setProfile(nextProfile)
      onProfileLoaded(nextProfile)
    } catch (loadError) {
      if (loadError instanceof ApiClientError && loadError.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setError(
        loadError instanceof ApiClientError
          ? loadError.message
          : "Unable to load profile.",
      )
    } finally {
      setIsLoading(false)
    }
  }, [accessToken, navigate, onProfileLoaded])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  useEffect(() => {
    localStorage.setItem(storageKey, activeTab)
  }, [activeTab, storageKey])

  return (
    <section className="main-view workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <h2>Profile</h2>
          </div>
          <button
            className="main-close-button"
            type="button"
            aria-label="Close"
            onClick={onClose}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6L18 18" />
              <path d="M18 6L6 18" />
            </svg>
          </button>
        </div>

        <nav className="workspace-tabs" aria-label="Profile tabs">
          {profileTabs.map((tab) => (
            <button
              className={`workspace-tab ${activeTab === tab.id ? "active" : ""}`}
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="workspace-content">
        {isLoading ? (
          <p className="contacts-state">Loading profile...</p>
        ) : error ? (
          <p className="contact-error" role="alert">
            {error}
          </p>
        ) : profile ? (
          activeTab === "overview" ? (
            <ProfilePage profile={profile} />
          ) : activeTab === "basic" ? (
            <UpdateProfilePage
              accessToken={accessToken}
              profile={profile}
              onUpdated={() => void loadProfile()}
            />
          ) : activeTab === "address" ? (
            <AddressProfilePage
              accessToken={accessToken}
              profile={profile}
              onUpdated={() => void loadProfile()}
            />
          ) : activeTab === "events" ? (
            <EventsProfilePage
              accessToken={accessToken}
              profile={profile}
              onUpdated={() => void loadProfile()}
            />
          ) : (
            <ProfilePicturePage
              accessToken={accessToken}
              profile={profile}
              onUpdated={() => void loadProfile()}
            />
          )
        ) : (
          <p className="contacts-state">No profile data available.</p>
        )}
      </div>
    </section>
  )
}

export default ProfileWorkspacePage
