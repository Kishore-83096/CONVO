import { type ReactNode } from "react";
import { Link } from "react-router-dom";

import { env } from "../utils/env";
import { ThemeToggle } from "./ThemeToggle";

type PublicLayoutProps = {
  children: ReactNode;
};

export function PublicLayout({ children }: PublicLayoutProps) {
  return (
    <div className="public-layout">
      <header className="public-header">
        <Link aria-label={`${env.appName} home`} className="brand-mark" to="/">
          <span aria-hidden="true" className="brand-mark__logo">
            {env.appName.slice(0, 1).toUpperCase()}
          </span>
          <span>{env.appName}</span>
        </Link>

        <nav aria-label="Public navigation" className="public-nav">
          <a href="/#features">Features</a>
          <a href="/#security">Security</a>
          <a href="/#flow">Flow</a>
          <a href="/#health">Health</a>
        </nav>

        <div className="public-header__actions">
          <ThemeToggle />
          <Link className="button ghost" to="/login">
            Login
          </Link>
          <Link className="button" to="/register">
            Register
          </Link>
        </div>
      </header>

      <main>{children}</main>
    </div>
  );
}
