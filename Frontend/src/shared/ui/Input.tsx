import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  hasError?: boolean;
};

export function Input({ hasError = false, className = "", ...props }: InputProps) {
  const classes = ["ui-input", hasError ? "ui-input--error" : "", className]
    .filter(Boolean)
    .join(" ");

  return <input className={classes} {...props} />;
}