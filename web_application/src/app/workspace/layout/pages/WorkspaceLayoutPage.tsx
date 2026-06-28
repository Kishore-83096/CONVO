import { useCallback, useEffect, useState } from "react"
import { Menu, MessageCircle, Sparkles, UsersRound } from "lucide-react"
import { useNavigate, useParams } from "react-router"

import { ApiClientError } from "@/api/client"
import AccountSettingsPage from "@/app/workspace/account/pages/AccountSettingsPage"
import type { ChatSummary } from "@/app/workspace/chats/chats.api"
import ChatListPage from "@/app/workspace/chats/pages/ChatListPage"
import ConversationPage from "@/app/workspace/chats/pages/ConversationPage"
import AddContactPage from "@/app/workspace/contacts/pages/AddContactPage"
import ConfirmActionModal from "@/app/workspace/layout/components/ConfirmActionModal"
import ProfileMenu from "@/app/workspace/layout/components/ProfileMenu"
import AppearancePage from "@/app/workspace/layout/pages/AppearancePage"
import EmptyPage from "@/app/workspace/layout/pages/EmptyPage"
import { getProfile } from "@/app/workspace/profile/profile.api"
import type { CompleteProfile } from "@/app/workspace/profile/profile.types"
import ProfileWorkspacePage from "@/app/workspace/profile/pages/ProfileWorkspacePage"
import StoriesPage from "@/app/workspace/stories/pages/StoriesPage"
import { logout } from "@/app/identity/auth/auth.api"
import { userHomePath } from "@/app/identity/auth/auth-routes"
import {
  clearAuthSession,
  getAuthSession,
} from "@/app/identity/auth/auth-session"
import {
  listContacts,
} from "@/app/identity/contacts/contacts.api"
import type { ContactSummary } from "@/app/identity/contacts/contacts.types"
import {
  ContactDetailPage,
  ContactsSidebar,
} from "@/app/identity/contacts"
import SeoMeta from "@/app/seo/SeoMeta"
import BrandThemeIcon from "@/components/BrandThemeIcon"
import { MessengerApiError } from "@/messenger/api/messenger-client"
import { listMessengerRooms } from "@/messenger/api/rooms.api"
import type { RoomListItem } from "@/messenger/api/messenger-api.types"
import DeviceRegistrationPage from "@/messenger/ui/DeviceRegistrationPage"

import "../css/WorkspaceLayout.css"

type SidebarView = "chats" | "stories" | "contacts" | "addContact" | "profileMenu"
type MainView =
  | "empty"
  | "chat"
  | "profile"
  | "account"
  | "appearance"
  | "contact"
  | "device"
type MobilePanel = "sidebar" | "main"

const themes = ["light", "dark", "blue", "pink", "lavender", "mint", "sunset", "aurora"]
const themeOptions = [
  { id: "light", name: "Light", colors: ["#fbfcff", "#e8edf5", "#2563eb"] },
  { id: "dark", name: "Dark", colors: ["#10141c", "#1f2937", "#8ab4ff"] },
  { id: "blue", name: "Blue", colors: ["#edf7ff", "#c5ddff", "#2563eb"] },
  { id: "pink", name: "Pink", colors: ["#fff1f6", "#f8c7dc", "#d94683"] },
  { id: "lavender", name: "Lavender", colors: ["#f7f2ff", "#d8c7ff", "#7c3aed"] },
  { id: "mint", name: "Mint", colors: ["#edfbf6", "#b9ead9", "#059669"] },
  { id: "sunset", name: "Sunset", colors: ["#fff7ed", "#fed7aa", "#ea580c"] },
  { id: "aurora", name: "Aurora", colors: ["#ecfeff", "#bbf7d0", "#0891b2"] },
]

function userStoragePrefix(session: ReturnType<typeof getAuthSession>) {
  if (!session) {
    return "myna.guest"
  }

  return `myna.user.${session.user.email}.${session.user.contact_number}`
}

function legacyUserStoragePrefix(session: ReturnType<typeof getAuthSession>) {
  if (!session) {
    return "convo.guest"
  }

  return `convo.user.${session.user.email}.${session.user.contact_number}`
}

function storageKey(prefix: string, name: string) {
  return `${prefix}.${name}`
}

function savedTheme(prefix: string) {
  const legacyPrefix = prefix.replace(/^myna/, "convo")
  const theme = getStoredValue(
    storageKey(prefix, "theme"),
    storageKey(legacyPrefix, "theme"),
  )
    ?? localStorage.getItem("convo.theme")
  return theme && themes.includes(theme) ? theme : "light"
}

function getStoredValue(key: string, legacyKey: string) {
  const value = localStorage.getItem(key)

  if (value) {
    return value
  }

  const legacyValue = localStorage.getItem(legacyKey)

  if (legacyValue) {
    localStorage.setItem(key, legacyValue)
  }

  return legacyValue
}

function savedSidebarView(prefix: string, legacyPrefix: string): SidebarView {
  const view = getStoredValue(
    storageKey(prefix, "sidebarView"),
    storageKey(legacyPrefix, "sidebarView"),
  )
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

function savedMainView(prefix: string, legacyPrefix: string): MainView {
  const view = getStoredValue(
    storageKey(prefix, "mainView"),
    storageKey(legacyPrefix, "mainView"),
  )
  const validViews: MainView[] = [
    "empty",
    "profile",
    "account",
    "appearance",
    "contact",
    "device",
  ]

  if (view === "contact" && !savedSelectedContactId(prefix, legacyPrefix)) {
    return "empty"
  }

  return validViews.includes(view as MainView) ? (view as MainView) : "empty"
}

function savedSelectedContactId(prefix: string, legacyPrefix: string) {
  const contactId = Number(
    getStoredValue(
      storageKey(prefix, "selectedContactId"),
      storageKey(legacyPrefix, "selectedContactId"),
    ),
  )

  return Number.isInteger(contactId) && contactId > 0 ? contactId : null
}

function formatChatTime(value: string | null) {
  if (!value) {
    return ""
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return ""
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}

function buildChatSummaries(
  rooms: RoomListItem[],
  contacts: ContactSummary[],
) {
  const contactsByUserId = new Map(
    contacts.map((contact) => [
      String(contact.contact_user_id),
      contact,
    ]),
  )

  return rooms.map((room) => {
    const matchedContactEntry = room.other_member_user_ids
      .map((userId) => contactsByUserId.get(String(userId)))
      .find(Boolean)
    const recipientUserId = matchedContactEntry
      ? String(matchedContactEntry.contact_user_id)
      : room.other_member_user_ids[0] ?? null
    const lastMessageAt =
      room.last_message?.created_at
      ?? room.updated_at
      ?? room.created_at

    return {
      id: room.id,
      roomId: room.id,
      roomType: room.room_type,
      name:
        matchedContactEntry?.saved_name
        || room.name
        || "Direct chat",
      status:
        room.room_type === "direct"
          ? "Direct message"
          : `${room.member_user_ids.length} members`,
      lastMessage: room.last_message
        ? "Encrypted message"
        : "No messages yet",
      time: formatChatTime(lastMessageAt),
      memberUserIds: room.member_user_ids,
      recipientUserId,
      contactId: matchedContactEntry?.id ?? null,
      profilePicture: matchedContactEntry?.profile_picture ?? null,
      lastMessageAt,
    } satisfies ChatSummary
  })
}

function WorkspaceLayoutPage() {
  const navigate = useNavigate()
  const { username } = useParams()
  const [session] = useState(() => getAuthSession())
  const userStorage = userStoragePrefix(session)
  const legacyUserStorage = legacyUserStoragePrefix(session)
  const [theme, setTheme] = useState(() => savedTheme(userStorage))
  const [sidebarView, setSidebarView] = useState<SidebarView>(() =>
    savedSidebarView(userStorage, legacyUserStorage),
  )
  const [mainView, setMainView] = useState<MainView>(() =>
    savedMainView(userStorage, legacyUserStorage),
  )
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("sidebar")
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null)
  const [chats, setChats] = useState<ChatSummary[]>([])
  const [isLoadingChats, setIsLoadingChats] = useState(true)
  const [chatError, setChatError] = useState("")
  const [selectedContactId, setSelectedContactId] = useState<number | null>(() =>
    savedSelectedContactId(userStorage, legacyUserStorage),
  )
  const [contactsRefreshKey, setContactsRefreshKey] = useState(0)
  const [completeProfile, setCompleteProfile] = useState<CompleteProfile | null>(null)
  const [isProfileLoading, setIsProfileLoading] = useState(true)
  const [profileError, setProfileError] = useState("")
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [isLogoutConfirmOpen, setIsLogoutConfirmOpen] = useState(false)
  const [logoutError, setLogoutError] = useState("")

  useEffect(() => {
    if (!session) {
      navigate("/", { replace: true })
      return
    }

    if (username !== session.user.username) {
      navigate(userHomePath(session), { replace: true })
    }
  }, [navigate, session, username])

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
      "device",
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

  const loadChats = useCallback(async () => {
    if (!session) {
      return
    }

    setIsLoadingChats(true)
    setChatError("")

    try {
      const [roomsResponse, contactsResponse] = await Promise.all([
        listMessengerRooms(session.accessToken),
        listContacts(session.accessToken),
      ])
      const nextChats = buildChatSummaries(
        roomsResponse.data ?? [],
        contactsResponse.data ?? [],
      )

      setChats(nextChats)
      setSelectedChat((current) => {
        if (!current) {
          return current
        }

        return nextChats.find((chat) => chat.id === current.id) ?? current
      })
    } catch (error) {
      if (
        (error instanceof ApiClientError || error instanceof MessengerApiError)
        && error.status === 401
      ) {
        clearAuthSession()
        navigate("/", { replace: true })
        return
      }

      setChatError(
        error instanceof MessengerApiError && error.status === 404
          ? "Rooms API is not available on the running messenger server. Restart the messenger backend."
          : error instanceof ApiClientError || error instanceof MessengerApiError
            ? error.message
            : "Unable to load chats.",
      )
    } finally {
      setIsLoadingChats(false)
    }
  }, [navigate, session])

  useEffect(() => {
    void loadMenuProfile()
  }, [loadMenuProfile])

  useEffect(() => {
    void loadChats()
  }, [loadChats, contactsRefreshKey])

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
      setIsLogoutConfirmOpen(false)
    }
  }

  return (
    <div className="desktop-layout" id="workspaceLayout">
      <SeoMeta
        canonicalPath={`/${session.user.username}`}
        description="Private Myna messaging workspace."
        robots="noindex, nofollow"
        title="Myna Private Workspace"
      />
      <aside className="sidebar" aria-label="Myna sidebar">
        <header className="sidebar-header">
          <div className="brand-lockup">
            <BrandThemeIcon className="brand-icon" theme={theme} />
            <h1 className="brand-name">Myna</h1>
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
              <UsersRound aria-hidden="true" />
            </button>

            <button
              className={`header-icon-button ${
                sidebarView === "profileMenu" ? "active" : ""
              }`}
              type="button"
              aria-label="Open profile menu"
              onClick={() => openSidebarView("profileMenu")}
            >
              <Menu aria-hidden="true" />
            </button>
          </nav>
        </header>

        <div className="sidebar-body">
          {sidebarView === "chats" ? (
            <ChatListPage
              chats={chats}
              errorMessage={chatError}
              isLoading={isLoadingChats}
              selectedChatId={selectedChat?.id ?? null}
              onOpenChat={openChat}
              onRefresh={() => void loadChats()}
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
              onOpenDevice={() => openMainView("device")}
              onOpenProfile={() => openMainView("profile")}
              onLogout={() => setIsLogoutConfirmOpen(true)}
            />
          ) : null}
        </div>

        <footer className="sidebar-footer">
          <button
            className={`footer-tab ${sidebarView === "chats" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("chats")}
          >
            <MessageCircle aria-hidden="true" />
            <span>Chats</span>
          </button>

          <button
            className={`footer-tab ${sidebarView === "stories" ? "active" : ""}`}
            type="button"
            onClick={() => openSidebarView("stories")}
          >
            <Sparkles aria-hidden="true" />
            <span>Stories</span>
          </button>
        </footer>
      </aside>

      <main className="main-body">
        {mainView === "empty" ? <EmptyPage /> : null}
        {mainView === "chat" && selectedChat ? (
          <ConversationPage
            accessToken={session.accessToken}
            chat={selectedChat}
            onClose={closeMainView}
            onMessageSent={() => void loadChats()}
          />
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
        {mainView === "device" ? (
          <DeviceRegistrationPage
            accessToken={session.accessToken}
            onClose={closeMainView}
            storageKey={storageKey(userStorage, "e2eeTab")}
          />
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

      <ConfirmActionModal
        confirmLabel="Logout"
        description="You will be signed out of this Myna session and returned to the welcome screen."
        isBusy={isLoggingOut}
        isOpen={isLogoutConfirmOpen}
        title="Logout from Myna?"
        tone="warning"
        onCancel={() => setIsLogoutConfirmOpen(false)}
        onConfirm={() => void handleLogout()}
      />
    </div>
  )
}

export default WorkspaceLayoutPage
