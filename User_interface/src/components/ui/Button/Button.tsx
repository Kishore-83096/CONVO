import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  leftIcon,
  rightIcon,
  children,
  className = "",
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  const classes = clsx(
    "ui-button",
    `ui-button--${variant}`,
    `ui-button--${size}`,
    {
      "ui-button--full-width": fullWidth,
      "ui-button--loading": loading,
    },
    className,
  );

  return (
    <button
      {...props}
      type={type}
      disabled={disabled || loading}
      className={classes}
      aria-busy={loading}
    >
      {loading ? (
        <span className="ui-button__spinner" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
            <path d="M12 2C6.47715 2 2 6.47715 2 12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </span>
      ) : leftIcon ? (
        <span className="ui-button__icon">{leftIcon}</span>
      ) : null}

      <span className="ui-button__label">
        {children}
      </span>

      {rightIcon && !loading && (
        <span className="ui-button__icon">{rightIcon}</span>
      )}
    </button>
  );
}