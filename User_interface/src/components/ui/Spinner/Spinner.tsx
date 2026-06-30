import clsx from "clsx";

import "./Spinner.css";

export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Spinner({
  size = "md",
  className,
}: SpinnerProps) {
  return (
    <span
      className={clsx(
        "ui-spinner",
        `ui-spinner--${size}`,
        className,
      )}
      aria-label="Loading"
      role="status"
    />
  );
}