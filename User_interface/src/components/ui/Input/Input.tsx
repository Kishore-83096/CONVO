import clsx from "clsx";
import {
  forwardRef,
  useId,
  useState,
  type InputHTMLAttributes,
} from "react";

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      id,
      label,
      helperText,
      error,
      fullWidth = false,
      className,
      required,
      type = "text",
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    
    // Setup ID associations for a11y
    const helperId = helperText ? `${inputId}-helper` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    const describedBy = [helperId, errorId].filter(Boolean).join(" ");

    // Internal state for password visibility
    const [showPassword, setShowPassword] = useState(false);
    const isPasswordType = type === "password";
    const currentType = isPasswordType ? (showPassword ? "text" : "password") : type;

    return (
      <div
        className={clsx("ui-input", {
          "ui-input--full-width": fullWidth,
        })}
      >
        {label && (
          <label htmlFor={inputId} className="ui-input__label">
            {label}
            {required && (
              <span className="ui-input__required" aria-hidden="true">*</span>
            )}
          </label>
        )}

        <div className="ui-input__wrapper">
          <input
            ref={ref}
            id={inputId}
            type={currentType}
            className={clsx(
              "ui-input__field",
              {
                "ui-input__field--error": Boolean(error),
                "ui-input__field--has-toggle": isPasswordType,
              },
              className,
            )}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy || undefined}
            {...props}
          />

          {isPasswordType && (
            <button
              type="button"
              className="ui-input__toggle"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              tabIndex={-1} // Prevent interrupting tab flow for quick form submission
            >
              {showPassword ? (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                  <line x1="1" y1="1" x2="23" y2="23"></line>
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              )}
            </button>
          )}
        </div>

        {helperText && !error && (
          <small id={helperId} className="ui-input__helper">
            {helperText}
          </small>
        )}

        {error && (
          <small id={errorId} className="ui-input__error" role="alert">
            {error}
          </small>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";