import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";

interface AuthCardProps {
  children: ReactNode;
}

export function AuthCard({ children }: AuthCardProps) {
  return (
    <div className="auth-card-container">
      <main className="auth-card">
        <Link
          to="/"
          className="auth-card__close"
          aria-label="Back to landing page"
          title="Back to landing page"
        >
          <X size={18} aria-hidden="true" />
        </Link>

        {children}
      </main>
    </div>
  );
}
