import {
  LogOut,
  UserCircle,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/use-auth";
import {
  userHomePath,
  userWorkspacePath,
} from "@/auth/auth-routes";
import { BrandLogo } from "@/components/brand";
import { Button } from "@/components/ui";

export function TopBar() {
  const navigate = useNavigate();

  const { logout, session } = useAuth();

  const user = session?.user;

  async function handleLogout() {
    try {
      await logout();

      navigate("/login", {
        replace: true,
      });
    } catch (error) {
      console.error("Logout failed:", error);
    }
  }

  return (
    <header className="top-bar">
      <button
        type="button"
        className="top-bar__brand"
        onClick={() => navigate(userHomePath(session))}
      >
        <BrandLogo />
      </button>

      <div className="top-bar__actions">
        {user && (
          <div className="top-bar__user" aria-label="Signed in user">
            <UserCircle size={22} aria-hidden="true" />

            <div className="top-bar__user-copy">
              <strong>{user.full_name}</strong>
              <span>
                @{user.username}
                {user.email ? ` · ${user.email}` : ""}
              </span>
            </div>
          </div>
        )}

        <div className="status-pill">
          Connected
        </div>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<Users size={16} aria-hidden="true" />}
          onClick={() => navigate(userWorkspacePath(session, "contacts"))}
        >
          Contacts
        </Button>

        <Button
          variant="secondary"
          size="sm"
          leftIcon={<LogOut size={16} aria-hidden="true" />}
          onClick={handleLogout}
        >
          Logout
        </Button>
      </div>
    </header>
  );
}



