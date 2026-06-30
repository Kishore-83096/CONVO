import type { ReactNode } from "react";

interface AuthCardProps {
  children: ReactNode;
}

export function AuthCard({ children }: AuthCardProps) {
  return (
    <div className="auth-card-container">
      <main className="auth-card">
        {children}
      </main>
    </div>
  );
}