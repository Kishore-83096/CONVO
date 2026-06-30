import {
  forwardRef,
  type InputHTMLAttributes,
} from "react";
import clsx from "clsx";

export interface TextFieldProps
  extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  fullWidth?: boolean;
}

const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  (
    {
      label,
      helperText,
      error,
      fullWidth = false,
      className,
      id,
      required,
      ...props
    },
    ref,
  ) => {
    const helperId = id ? `${id}-helper` : undefined;

    return (
      <div
        className={clsx("text-field", {
          "text-field--full": fullWidth,
        })}
      >
        {label && (
          <label htmlFor={id} className="text-field__label">
            {label}

            {required && (
              <span
                aria-hidden="true"
                className="text-field__required"
              >
                *
              </span>
            )}
          </label>
        )}

        <input
          {...props}
          ref={ref}
          id={id}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={helperId}
          className={clsx(
            "text-field__input",
            {
              "text-field__input--error": Boolean(error),
            },
            className,
          )}
        />

        {(helperText || error) && (
          <small
            id={helperId}
            className={clsx("text-field__helper", {
              "text-field__helper--error": Boolean(error),
            })}
          >
            {error ?? helperText}
          </small>
        )}
      </div>
    );
  },
);

TextField.displayName = "TextField";

export default TextField;