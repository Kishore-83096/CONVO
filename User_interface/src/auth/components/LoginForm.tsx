import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import {
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useState } from "react";

import { useAuth } from "@/auth/use-auth";
import {
  loginSchema,
  type LoginFormValues,
} from "@/auth/validation/login-schema";
import { Button, Input } from "@/components/ui";

import { AuthLogo } from "./AuthLogo";

export function LoginForm() {
  const navigate = useNavigate();
  const location = useLocation();

  const { login } = useAuth();

  const [loginError, setLoginError] =
    useState("");

  const {
    register,
    handleSubmit,
    control,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),

    defaultValues: {
      method: "username",
      identifier:
        location.state?.username ?? "",
      password: "",
    },
  });

  const currentMethod = useWatch({
    control,
    name: "method",
  });

  const getIdentifierInputMode = () => {
    switch (currentMethod) {
      case "contact_number":
        return "tel";

      case "email":
        return "email";

      default:
        return "text";
    }
  };

  async function onSubmit(
    data: LoginFormValues,
  ) {
    setLoginError("");

    try {
      await login(data);

      navigate("/app", {
        replace: true,
      });
    } catch (error) {
      console.error(
        "Login failed:",
        error,
      );

      setLoginError(
        error instanceof Error
          ? error.message
          : "Unable to sign in.",
      );
    }
  }

  return (
    <>
      <AuthLogo />

      {location.state
        ?.registrationSuccess && (
        <div
          className="auth-success-banner"
          role="status"
          aria-live="polite"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>

          <span>
            Account created
            successfully. Please sign
            in.
          </span>
        </div>
      )}

      {loginError && (
        <div
          className="auth-error-banner"
          role="alert"
          aria-live="assertive"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
            />

            <line
              x1="12"
              y1="8"
              x2="12"
              y2="12"
            />

            <line
              x1="12"
              y1="16"
              x2="12.01"
              y2="16"
            />
          </svg>

          <span>{loginError}</span>
        </div>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <fieldset
          disabled={isSubmitting}
          style={{
            border: "none",
            padding: 0,
            margin: 0,
          }}
        >
          <div className="auth-form__field">
            <label
              htmlFor="method"
              className="auth-form__label"
            >
              Login Method
            </label>

            <div className="auth-form__select-wrapper">
              <select
                id="method"
                className="auth-form__select"
                aria-invalid={Boolean(
                  errors.method,
                )}
                {...register("method")}
              >
                <option value="username">
                  Username
                </option>

                <option value="email">
                  Email
                </option>

                <option value="contact_number">
                  Contact Number
                </option>
              </select>
            </div>
          </div>

          <div
            style={{
              marginTop:
                "var(--spacing-md)",
            }}
          >
            <Input
              label="Identifier"
              placeholder="Username, Email or Contact Number"
              fullWidth
              autoComplete="username"
              inputMode={getIdentifierInputMode()}
              error={
                errors.identifier
                  ?.message
              }
              {...register("identifier")}
            />
          </div>

          <div
            style={{
              marginTop:
                "var(--spacing-md)",
            }}
          >
            <Input
              type="password"
              label="Password"
              placeholder="Enter your password"
              fullWidth
              autoComplete="current-password"
              error={
                errors.password?.message
              }
              {...register("password")}
            />
          </div>

          <div
            style={{
              marginTop:
                "var(--spacing-lg)",
            }}
          >
            <Button
              type="submit"
              fullWidth
              size="lg"
              loading={isSubmitting}
            >
              Sign In
            </Button>
          </div>
        </fieldset>

        <p className="auth-form__footer">
          Don't have an account?{" "}
          <Link
            to="/register"
            className="auth-form__link"
          >
            Create Account
          </Link>
        </p>
      </form>
    </>
  );
}
