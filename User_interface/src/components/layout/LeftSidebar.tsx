import {
  Contact,
  LogOut,
  MessageCircle,
  Settings,
  UserCircle,
  UsersRound,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/use-auth";
import {
  userHomePath,
  userWorkspacePath,
} from "@/auth/auth-routes";
import { BrandLogo } from "@/components/brand";

function displayName(
  user: { full_name?: string; username?: string } | undefined,
) {
  return user?.full_name || user?.username || "MYNA user";
}

export function LeftSidebar() {
  const navigate = useNavigate();
  const { logout, session } = useAuth();
  const user = session?.user;
  const navItems = [
    {
      icon: MessageCircle,
      label: "Chats",
      to: userHomePath(session),
    },
    {
      icon: Contact,
      label: "Contacts",
      to: userWorkspacePath(session, "contacts"),
    },
    {
      icon: UserCircle,
      label: "Profile",
      to: userWorkspacePath(session, "profile"),
    },
    {
      icon: Settings,
      label: "Settings",
      to: userWorkspacePath(session, "settings"),
    },
  ];

  async function handleLogout() {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (error) {
      console.error("Logout failed:", error);
    }
  }

  return (
    <aside className="left-rail" aria-label="MYNA sidebar">
      <header className="sidebar-header">
        <button
          className="sidebar-brand-button"
          type="button"
          onClick={() => navigate(userHomePath(session))}
        >
          <BrandLogo />
        </button>

        <button
          className="header-icon-button"
          type="button"
          aria-label="Open contacts"
          title="Contacts"
          onClick={() => navigate(userWorkspacePath(session, "contacts"))}
        >
          <UsersRound aria-hidden="true" />
        </button>
      </header>

      <div className="sidebar-profile">
        <div className="profile-avatar" aria-hidden="true">
          {displayName(user).slice(0, 2).toUpperCase()}
        </div>
        <div className="profile-summary-copy">
          <strong>{displayName(user)}</strong>
          {user?.username && <span>@{user.username}</span>}
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Workspace navigation">
        {navItems.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              className={({ isActive }) =>
                `profile-menu-button${isActive ? " active" : ""}`
              }
              key={item.to}
              to={item.to}
            >
              <Icon aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <footer className="sidebar-footer">
        <button
          className="profile-menu-button danger-text"
          type="button"
          onClick={handleLogout}
        >
          <LogOut aria-hidden="true" />
          <span>Logout</span>
        </button>
      </footer>
    </aside>
  );
}
