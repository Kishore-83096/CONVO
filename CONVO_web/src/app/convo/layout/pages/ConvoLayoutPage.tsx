import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { ApiClientError } from "@/api/client"
import AccountSettingsPage from "@/app/convo/account/pages/AccountSettingsPage"
import { demoChats, type ChatSummary } from "@/app/convo/chats/chats.api"
import ChatListPage from "@/app/convo/chats/pages/ChatListPage"
import ConversationPage from "@/app/convo/chats/pages/ConversationPage"
import AddContactPage from "@/app/convo/contacts/pages/AddContactPage"
import ProfileMenu from "@/app/convo/layout/components/ProfileMenu"
import AppearancePage from "@/app/convo/layout/pages/AppearancePage"
import EmptyPage from "@/app/convo/layout/pages/EmptyPage"
import { getProfile } from "@/app/convo/profile/profile.api"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"
import ProfileWorkspacePage from "@/app/convo/profile/pages/ProfileWorkspacePage"
import StoriesPage from "@/app/convo/stories/pages/StoriesPage"
import { logout } from "@/app/parrot_identity/auth/auth.api"
import {
  clearAuthSession,
  getAuthSession,
} from "@/app/parrot_identity/auth/auth-session"
import {
  ContactDetailPage,
  ContactsSidebar,
} from "@/app/parrot_identity/contacts"
import convoLogo from "@/assets/convo/CONVO.png"

import "../css/ConvoLayout.css"

type SidebarView = "chats" | "stories" | "contacts" | "addContact" | "profileMenu"
type MainView = "empty" | "chat" | "profile" | "account" | "appearance" | "contact"
type MobilePanel = "sidebar" | "main"

const themes = ["light", "dark", "blue", "pink", "lavender", "mint", "sunset", "aurora"]
const themeOptions = [
  { id: "light", name: "Light", colors: ["#ffffff", "#f3f5f8", "#22262d"] },
  { id: "dark", name: "Dark", colors: ["#11151b", "#1b2029", "#f1f4f8"] },
  { id: "blue", name: "Blue", colors: ["#eef6ff", "#b9d8f7", "#2d70b8"] },
  { id: "pink", name: "Pink", colors: ["#fff2f7", "#e9bdd2", "#b85880"] },
  { id: "lavender", name: "Lavender", colors: ["#f8f3ff", "#cfbde9", "#7759b1"] },
  { id: "mint", name: "Mint", colors: ["#effaf6", "#b9ddcf", "#4d9278"] },
  { id: "sunset", name: "Sunset", colors: ["#fff8ee", "#e7c79a", "#b67832"] },
  { id: "aurora", name: "Aurora", colors: ["#effbfc", "#b7dade", "#438993"] },
]

function userStoragePrefix(session: ReturnType<typeof getAuthSession>) {
  if (!session) {
    return "convo.guest"
  }

  return `convo.user.${session.user.email}.${session.user.contact_number}`
}

function storageKey(prefix: string, name: string) {
  return `${prefix}.${name}`
}

function savedTheme(prefix: string) {
  const theme = localStorage.getItem(storageKey(prefix, "theme"))
    ?? localStorage.getItem("convo.theme")
  return theme && themes.includes(theme) ? theme : "light"
}

function savedSidebarView(prefix: string): SidebarView {
  const view = localStorage.getItem(storageKey(prefix, "sidebarView"))
  const validViews: SidebarView[] = [
    "chats",
    "stories",
    "contacts",
    "addContact",
    "profileMenu",
  ]

  return validViews.includes(view as SidebarView)
    ? (view as SidebarView)
    : "chats"
}

function savedMainView(prefix: string): MainView {
  const view = localStorage.getItem(storageKey(prefix, "mainView"))
  const validViews: MainView[] = ["empty", "profile", "account", "appearance", "contact"]

  if (view === "contact" && !savedSelectedContactId(prefix)) {
    return "empty"
  }

  return validViews.includes(view as MainView) ? (view as MainView) : "empty"
}

function savedSelectedContactId(prefix: string) {
  const contactId = Number(localStorage.getItem(storageKey(prefix, "selectedContactId")))

  return Number.isInteger(contactId) && contactId > 0 ? contactId : null
}

function ConvoLayoutPage() {
  const navigate = useNavigate()
  const [session] = useState(() => getAuthSession())
  const userStorage = userStoragePrefix(session)
  const [theme, setTheme] = useState(() => savedTheme(userStorage))
  const [sidebarView, setSidebarView] = useState<SidebarView>(() =>
    savedSidebarView(userStorage),
  )
  const [mainView, setMainView] = useState<MainView>(() =>
    savedMainView(userStorage),
  )
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("sidebar")
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null)
  const [selectedContactId, setSelectedContactId] = useState<number | null>(() =>
    savedSelectedContactId(userStorage),
  )
  const [contactsRefreshKey, setContactsRefreshKey] = useState(0)
  const [completeProfile, setCompleteProfile] = useState<CompleteProfile | null>(null)
  const [isProfileLoading, setIsProfileLoading] = useState(true)
  const [profileError, setProfileError] = useState("")
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState("")

  useEffect(() => {
    if (!session) {
      navigate("/", { replace: true })
    }
  }, [navigate, session])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(storageKey(userStorage, "theme"), theme)
  }, [theme, userStorage])

  useEffect(() => {
    localStorage.setItem(storageKey(userStorage, "sidebarView"), sidebarView)
  }, [sidebarView, userStorage])

  useEffect(() => {
    const restorableMainView: MainView[] = [
      "empty",
      "profile",
      "account",
      "appearance",
      "contact",
    ]

    localStorage.setItem(
      storageKey(userStorage, "mainView"),
      restorableMainView.includes(mainView) &&
        (mainView !== "contact" || selectedContactId)
        ? mainView
        : "empty",
    )
  }, [mainView, selectedContactId, userStorage])

  useEffect(() => {
    if (selectedContactId) {
      localStorage.setItem(
        storageKey(userStorage, "selectedContactId"),
        String(selectedContactId),
      )
      return
    }

    localStorage.removeItem(storageKey(userStorage, "selectedContactId"))
  }, [selectedContactId, userStorage])

  useEffect(() => {
    document.documentElement.dataset.mobilePanel = mobilePanel
  }, [mobilePanel])

  const loadMenuProfile = useCallback(async () => {
    if (!session) {
      return
    }

    setIsProfileLoading(true)
    setProfileError("")

    try {
      const response = await getProfile(session.accessToken)
      setCompleteProfile(response.data ?? null)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setProfileError(
        error instanceof ApiClientError
          ? error.message
          : "Unable to load profile menu details.",
      )
    } finally {
      setIsProfileLoading(false)
    }
  }, [navigate, session])

  useEffect(() => {
    void loadMenuProfile()
  }, [loadMenuProfile])

  if (!session) {
    return null
  }

  const openSidebarView = (view: SidebarView) => {
    setSidebarView(view)
    setMobilePanel("sidebar")
  }

  const openChat = (chat: ChatSummary) => {
    setSelectedChat(chat)
    setSelectedContactId(null)
    setMainView("chat")
    setMobilePanel("main")
  }

  const openContact = (contactId: number) => {
    setSelectedContactId(contactId)
    setSelectedChat(null)
    setMainView("contact")
    setMobilePanel("main")
  }

  const openMainView = (view: MainView) => {
    setMainView(view)
    setSelectedChat(null)
    setSelectedContactId(null)
    setMobilePanel("main")
  }

  const closeMainView = () => {
    setMainView("empty")
    setSelectedChat(null)
    setSelectedContactId(null)
    setMobilePanel("sidebar")
  }

  const handleLogout = async () => {
    setIsLoggingOut(true)
    setLogoutError("")

    try {
      await logout(session.accessToken)
      navigate("/", { replace: true })
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setLogoutError(
        error instanceof ApiClientError
          ? error.message
          : "Unable to log out. Please try again.",
      )
    } finally {
      setIsLoggingOut(false)
    }
  }

  return (
    <div className="desktop-layout" id="convoLayout">
      <aside className="sidebar" aria-label="CONVO sidebar">
        <header className="sidebar-header">
          <div className="brand-lockup">
            <img className="brand-icon" src={convoLogo} alt="CONVO logo" />
            <h1 className="brand-name">CONVO</h1>
          </div>

          <nav className="header-actions" aria-label="Sidebar actions">
            <button
              className={`header-icon-button ${
                sidebarView === "contacts" || sidebarView === "addContact"
                  ? "active"
                  : ""
              }`}
              type="button"
              aria-label="Open contacts"
              title="Contacts"
              onClick={() => openSidebarView("contacts")}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5V19" />
                <path d="M5 12H19" />
              </svg>
            </button>

            <button
              className={`header-icon-button ${
                sidebarView === "profileMenu" ? "active" : ""
              }`}
              type="button"
              aria-label="Open profile menu"
              onClick={() => openSidebarView("profileMenu")}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 7H20" />
                <path d="M4 12H20" />
                <path d="M4 17H20" />
              </svg>
            </button>
          </nav>
        </header>

        <div className="sidebar-body">
          {sidebarView === "chats" ? (
            <ChatListPage
              chats={demoChats}
              selectedChatId={selectedChat?.id ?? null}
              onOpenChat={openChat}
            />
          ) : null}
          {sidebarView === "stories" ? <StoriesPage /> : null}
          {sidebarView === "contacts" ? (
            <section className="sidebar-view active" aria-label="Saved contacts tab">
              <ContactsSidebar
                accessToken={session.accessToken}
                onAddContact={() => openSidebarView("addContact")}
                onSelectContact={openContact}
                refreshKey={contactsRefreshKey}
                selectedContactId={selectedContactId}
              />
            </section>
          ) : null}
          {sidebarView === "addContact" ? (
            <AddContactPage
              accessToken={session.accessToken}
              onAdded={() => {
                setContactsRefreshKey((current) => current + 1)
                openSidebarView("contacts")
              }}
              onViewContacts={() => openSidebarView("contacts")}
            />
          ) : null}
          {sidebarView === "profileMenu" ? (
            <ProfileMenu
              activeMainView={mainView}
              currentTheme={theme}
              isLoggingOut={isLoggingOut}
              isProfileLoading={isProfileLoading}
              logoutError={logoutError}
              profile={completeProfile}
              profileError={profileError}
              session={session}
              onOpenAppearance={() => openMainView("appearance")}
              onOpenAccount={() => openMainView("account")}
              onOpenProfile={() => openMainView("profile")}
              onLogout={() => void handleLogout()}
            />
          ) : null}
        </div>

        <footer className="sidebar-footer">
          <button
            className={`footer-tab ${sidebarView === "chats" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("chats")}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 5H20V16H9L4 20V5Z" />
            </svg>
            <span>Chats</span>
          </button>

          <button
            className={`footer-tab ${sidebarView === "stories" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("stories")}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            <span>Stories</span>
          </button>
        </footer>
      </aside>

      <main className="main-body">
        {mainView === "empty" ? <EmptyPage /> : null}
        {mainView === "chat" && selectedChat ? (
          <ConversationPage chat={selectedChat} onClose={closeMainView} />
        ) : null}
        {mainView === "contact" && selectedContactId ? (
          <section className="main-view workspace-view active">
            <ContactDetailPage
              accessToken={session.accessToken}
              contactId={selectedContactId}
              onBack={closeMainView}
              onChanged={() => setContactsRefreshKey((current) => current + 1)}
            />
          </section>
        ) : null}
        {mainView === "profile" ? (
          <ProfileWorkspacePage
            accessToken={session.accessToken}
            initialProfile={completeProfile}
            onClose={closeMainView}
            onProfileLoaded={setCompleteProfile}
            storageKey={storageKey(userStorage, "profileTab")}
          />
        ) : null}
        {mainView === "account" ? (
          <AccountSettingsPage
            accessToken={session.accessToken}
            profile={completeProfile}
            session={session}
            onClose={closeMainView}
            storageKey={storageKey(userStorage, "accountTab")}
          />
        ) : null}
        {mainView === "appearance" ? (
          <AppearancePage
            currentTheme={theme}
            themes={themeOptions}
            onClose={closeMainView}
            onThemeChange={setTheme}
          />
        ) : null}
      </main>
    </div>
  )
}

export default ConvoLayoutPage
