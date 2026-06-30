import type {
  HTMLAttributes,
  ReactNode,
} from "react";

import clsx from "clsx";

import "./Card.css";

export interface CardProps
  extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: "none" | "sm" | "md" | "lg";
  bordered?: boolean;
  elevated?: boolean;
}

export function Card({
  children,
  className,
  padding = "md",
  bordered = true,
  elevated = false,
  ...props
}: CardProps) {
  return (
    <div
      {...props}
      className={clsx(
        "ui-card",
        `ui-card--padding-${padding}`,
        {
          "ui-card--bordered": bordered,
          "ui-card--elevated": elevated,
        },
        className,
      )}
    >
      {children}
    </div>
  );
}