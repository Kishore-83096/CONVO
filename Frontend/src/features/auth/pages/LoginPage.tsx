import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import { PublicLayout } from "../../../shared/ui/PublicLayout";
import { useLoginUser } from "../hooks";
import { loginSchema, type LoginFormValues } from "../schemas";
import type {
  LoginFieldName,
  LoginMethod,
  LoginRequest,
  RegisterResponseData,
} from "../types";

type RouterState = {
  from?: {
    pathname?: string;
  };
  message?: string;
  registrationSuccess?: boolean;
  registeredUser?: RegisterResponseData;
};

const loginFieldNames: LoginFieldName[] = ["method", "identifier", "password"];

function getFirstErrorMessage(value: unknown): string | undefined {
  if (Array.isArray(value)) {
    const first = value[0];
    return typeof first === "string" ? first : undefined;
  }

  if (typeof value === "string") {
    return value;
  }

  return undefined;
}

function isErrorMap(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeIdentifier(method: LoginMethod, identifier: string): string {
  const trimmedIdentifier = identifier.trim();

  if (method === "username") {
    return trimmedIdentifier.replace(/^@+/, "").toLowerCase();
  }

  if (method === "email") {
    return trimmedIdentifier.toLowerCase();
  }

  return trimmedIdentifier;
}

export function LoginPage() {
  const [serverMessage, setServerMessage] = useState("");

  const navigate = useNavigate();
  const location = useLocation();
  const { saveSession } = useAuth();

  const loginMutation = useLoginUser();

  const state = location.state as RouterState | null;
  const redirectedFrom = state?.from?.pathname;
  const routeMessage = state?.message;
  const registeredUser = state?.registrationSuccess
    ? state.registeredUser
    : undefined;
  const redirectTarget = redirectedFrom ?? "/app";
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      method: "username",
      identifier: registeredUser?.username ?? "",
      password: "",
    },
  });

  const selectedMethod = useWatch({
    control,
    name: "method",
  });

  async function onSubmit(values: LoginFormValues) {
    setServerMessage("");

    const payload: LoginRequest = {
      method: values.method,
      identifier: normalizeIdentifier(values.method, values.identifier),
      password: values.password,
    };

    const result = await loginMutation.mutateAsync(payload);

    if (result.ok) {
      await saveSession({
        accessToken: result.data.access_token,
        tokenType: result.data.token_type,
        expiresAt: result.data.expires_at,
        user: result.data.user,
      });

      navigate(redirectTarget, {
        replace: true,
      });

      return;
    }

    setServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of loginFieldNames) {
        const message = getFirstErrorMessage(result.errors[fieldName]);

        if (message) {
          setError(fieldName, {
            type: "server",
            message,
          });
        }
      }
    }
  }

  const isBusy = isSubmitting || loginMutation.isPending;

  return (
    <PublicLayout>
      <section className="auth-public-page">
        <div className="auth-card">
          <p className="eyebrow">Sprint 1 · Phase 1.2</p>

          <h1>Login securely</h1>

          <p>
            Login with your username, generated email, or generated contact
            number. After successful login, the JWT and current user are stored
            in IndexedDB.
          </p>

          {redirectedFrom ? (
            <div className="notice">
              You tried to open <strong>{redirectedFrom}</strong>. Login is
              required before opening that route.
            </div>
          ) : null}
          {routeMessage ? <div className="notice">{routeMessage}</div> : null}

          {registeredUser ? (
            <div className="auth-success" role="status">
              <strong>Account created successfully.</strong>
              <p>Login with your generated details.</p>

              <dl className="auth-result-list">
                <div>
                  <dt>Username</dt>
                  <dd>{registeredUser.username}</dd>
                </div>

                <div>
                  <dt>Generated email</dt>
                  <dd>{registeredUser.email}</dd>
                </div>

                <div>
                  <dt>Generated contact number</dt>
                  <dd>{registeredUser.contact_number}</dd>
                </div>
              </dl>
            </div>
          ) : null}

          <form className="auth-form" onSubmit={handleSubmit(onSubmit)}>
            <FormField
              error={errors.method?.message}
              htmlFor="method"
              label="Login method"
            >
              <select
                className="ui-input"
                id="method"
                {...register("method")}
              >
                <option value="username">Username</option>
                <option value="email">Generated email</option>
                <option value="contact_number">Contact number</option>
              </select>
            </FormField>

            <FormField
              error={errors.identifier?.message}
              hint={
                selectedMethod === "username"
                  ? "Example: grace_hopper"
                  : selectedMethod === "email"
                    ? "Use your generated email."
                    : "Example: 7467449164"
              }
              htmlFor="identifier"
              label={
                selectedMethod === "username"
                  ? "Username"
                  : selectedMethod === "email"
                    ? "Generated email"
                    : "Contact number"
              }
            >
              <Input
                autoComplete="username"
                hasError={Boolean(errors.identifier)}
                id="identifier"
                placeholder={
                  selectedMethod === "username"
                    ? "grace_hopper"
                    : selectedMethod === "email"
                      ? "Generated email"
                      : "7467449164"
                }
                {...register("identifier")}
              />
            </FormField>

            <FormField
              error={errors.password?.message}
              htmlFor="password"
              label="Password"
            >
              <Input
                autoComplete="current-password"
                hasError={Boolean(errors.password)}
                id="password"
                placeholder="StrongPass123!"
                type="password"
                {...register("password")}
              />
            </FormField>

            {serverMessage ? (
              <div className="auth-error" role="alert">
                {serverMessage}
              </div>
            ) : null}

            <Button disabled={isBusy} fullWidth type="submit">
              {isBusy ? "Logging in..." : "Login"}
            </Button>
          </form>

          <div className="auth-success" role="status">
            <strong>Phase 1.2 scope</strong>
            <p>
              This phase only logs in and saves the Identity session. Messenger
              device registration, recovery, and WebSocket startup will be added
              in later phases.
            </p>
          </div>

          <div className="hero-actions">
            <Link className="button secondary" to="/register">
              Create account
            </Link>

            <Link className="button ghost" to="/">
              Back home
            </Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
