import { useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/use-auth";
import { Button } from "@/components/ui";

export function TopBar() {
  const navigate = useNavigate();

  const { logout } = useAuth();

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
      <h2>Myna</h2>

      <div className="top-bar__actions">
        <div className="status-pill">
          Connected
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={handleLogout}
        >
          Logout
        </Button>
      </div>
    </header>
  );
}


