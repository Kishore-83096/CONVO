import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import { LogoutButton } from "../../auth/components/LogoutButton";
import { useDeleteAccount, useResetPassword } from "../../auth/hooks";
import {
  deleteAccountSchema,
  resetPasswordSchema,
} from "../../auth/schemas";
import type {
  DeleteAccountFieldName,
  DeleteAccountFormValues,
  DeleteAccountRequest,
  ResetPasswordFieldName,
  ResetPasswordFormValues,
  ResetPasswordRequest,
} from "../../auth/types";

const resetPasswordFieldNames: ResetPasswordFieldName[] = [
  "username",
  "email",
  "contact_number",
  "current_password",
  "new_password",
  "confirm_new_password",
];

const deleteAccountFieldNames: DeleteAccountFieldName[] = [
  "username",
  "email",
  "contact_number",
  "current_password",
  "confirmation_text",
];

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

export function SettingsPage() {
  const [resetServerMessage, setResetServerMessage] = useState("");
  const [deleteServerMessage, setDeleteServerMessage] = useState("");

  const navigate = useNavigate();
  const { user, clearSession } = useAuth();

  const resetPasswordMutation = useResetPassword();
  const deleteAccountMutation = useDeleteAccount();

  const {
    register: registerResetField,
    handleSubmit: handleResetSubmit,
    setError: setResetError,
    reset: resetPasswordForm,
    formState: {
      errors: resetErrors,
      isSubmitting: isResetSubmitting,
    },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      username: "",
      email: "",
      contact_number: "",
      current_password: "",
      new_password: "",
      confirm_new_password: "",
    },
  });

  const {
    register: registerDeleteField,
    handleSubmit: handleDeleteSubmit,
    setError: setDeleteError,
    reset: resetDeleteForm,
    formState: {
      errors: deleteErrors,
      isSubmitting: isDeleteSubmitting,
    },
  } = useForm<DeleteAccountFormValues>({
    resolver: zodResolver(deleteAccountSchema),
    defaultValues: {
      username: "",
      email: "",
      contact_number: "",
      current_password: "",
      confirmation_text: "",
    },
  });

  async function redirectMissingSession() {
    await clearSession();

    navigate("/login", {
      replace: true,
      state: {
        message: "Your session was not found. Please login again.",
      },
    });
  }

  async function onResetPasswordSubmit(values: ResetPasswordFormValues) {
    setResetServerMessage("");

    if (!user) {
      setResetServerMessage("Your session was not found. Please login again.");
      await redirectMissingSession();
      return;
    }

    const payload: ResetPasswordRequest = {
      username: values.username,
      email: values.email,
      contact_number: values.contact_number,
      current_password: values.current_password,
      new_password: values.new_password,
      confirm_new_password: values.confirm_new_password,
    };

    const result = await resetPasswordMutation.mutateAsync(payload);

    if (result.ok) {
      resetPasswordForm();

      await clearSession();

      navigate("/login", {
        replace: true,
        state: {
          message:
            "Password reset successfully. All sessions were cleared. Please login with your new password.",
        },
      });

      return;
    }

    setResetServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of resetPasswordFieldNames) {
        const message = getFirstErrorMessage(result.errors[fieldName]);

        if (message) {
          setResetError(fieldName, {
            type: "server",
            message,
          });
        }
      }
    }
  }

  async function onDeleteAccountSubmit(values: DeleteAccountFormValues) {
    setDeleteServerMessage("");

    if (!user) {
      setDeleteServerMessage("Your session was not found. Please login again.");
      await redirectMissingSession();
      return;
    }

    const payload: DeleteAccountRequest = {
      username: values.username,
      email: values.email,
      contact_number: values.contact_number,
      current_password: values.current_password,
    };

    const result = await deleteAccountMutation.mutateAsync(payload);

    if (result.ok) {
      resetDeleteForm();

      await clearSession();

      navigate("/login", {
        replace: true,
        state: {
          message:
            "Your account was deleted successfully. Create a new account if you want to use Myna again.",
        },
      });

      return;
    }

    setDeleteServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of deleteAccountFieldNames) {
        const message = getFirstErrorMessage(result.errors[fieldName]);

        if (message) {
          setDeleteError(fieldName, {
            type: "server",
            message,
          });
        }
      }
    }
  }

  const isResetBusy = isResetSubmitting || resetPasswordMutation.isPending;
  const isDeleteBusy = isDeleteSubmitting || deleteAccountMutation.isPending;

  return (
    <main className="app-shell-page">
      <section className="app-shell-card">
        <div>
          <p className="eyebrow">Sprint 1 · Phase 1.5</p>
          <h1>Settings</h1>
          <p>
            Manage your authenticated Identity account. Sensitive actions now
            require you to manually type your username, generated email, contact
            number, and password.
          </p>
        </div>

        {user ? (
          <div className="session-card">
            <h2>Logged in session</h2>

            <p>
              You are logged in, but reset password and delete account will not
              silently use this saved session identity. You must manually type
              your account details in the forms below.
            </p>

            <dl className="auth-result-list">
              <div>
                <dt>Current session username</dt>
                <dd>{user.username}</dd>
              </div>

              <div>
                <dt>Current session email</dt>
                <dd>{user.email}</dd>
              </div>

              <div>
                <dt>Current session contact number</dt>
                <dd>{user.contactNumber}</dd>
              </div>
            </dl>
          </div>
        ) : null}

        <div className="settings-section">
          <div>
            <h2>Reset password</h2>
            <p>
              Type your account details manually. This makes the action
              intentional and confirms you know the account identity before
              changing the password.
            </p>
          </div>

          <form
            className="auth-form"
            onSubmit={handleResetSubmit(onResetPasswordSubmit)}
          >
            <FormField
              error={resetErrors.username?.message}
              hint="Example: grace_hopper"
              htmlFor="reset_username"
              label="Username"
            >
              <Input
                autoComplete="username"
                hasError={Boolean(resetErrors.username)}
                id="reset_username"
                placeholder="grace_hopper"
                {...registerResetField("username")}
              />
            </FormField>

            <FormField
              error={resetErrors.email?.message}
              hint="Example: grace_hopper@myna.com"
              htmlFor="reset_email"
              label="Generated email"
            >
              <Input
                autoComplete="email"
                hasError={Boolean(resetErrors.email)}
                id="reset_email"
                placeholder="grace_hopper@myna.com"
                type="email"
                {...registerResetField("email")}
              />
            </FormField>

            <FormField
              error={resetErrors.contact_number?.message}
              hint="Exactly 10 digits."
              htmlFor="reset_contact_number"
              label="Contact number"
            >
              <Input
                autoComplete="tel"
                hasError={Boolean(resetErrors.contact_number)}
                id="reset_contact_number"
                inputMode="numeric"
                placeholder="7467449164"
                {...registerResetField("contact_number")}
              />
            </FormField>

            <FormField
              error={resetErrors.current_password?.message}
              htmlFor="reset_current_password"
              label="Current password"
            >
              <Input
                autoComplete="current-password"
                hasError={Boolean(resetErrors.current_password)}
                id="reset_current_password"
                placeholder="Current password"
                type="password"
                {...registerResetField("current_password")}
              />
            </FormField>

            <FormField
              error={resetErrors.new_password?.message}
              hint="Use 8–128 characters. Do not reuse your current password."
              htmlFor="new_password"
              label="New password"
            >
              <Input
                autoComplete="new-password"
                hasError={Boolean(resetErrors.new_password)}
                id="new_password"
                placeholder="NewStrongPass123!"
                type="password"
                {...registerResetField("new_password")}
              />
            </FormField>

            <FormField
              error={resetErrors.confirm_new_password?.message}
              htmlFor="confirm_new_password"
              label="Confirm new password"
            >
              <Input
                autoComplete="new-password"
                hasError={Boolean(resetErrors.confirm_new_password)}
                id="confirm_new_password"
                placeholder="NewStrongPass123!"
                type="password"
                {...registerResetField("confirm_new_password")}
              />
            </FormField>

            {resetServerMessage ? (
              <div className="auth-error" role="alert">
                {resetServerMessage}
              </div>
            ) : null}

            <Button disabled={isResetBusy} fullWidth type="submit">
              {isResetBusy ? "Resetting password..." : "Reset password"}
            </Button>
          </form>
        </div>

        <div className="danger-zone">
          <div>
            <p className="eyebrow">Danger zone</p>
            <h2>Delete account</h2>
            <p>
              Type your account details manually before deleting. Use only a
              test account while developing because this permanently deletes the
              user from the Identity database.
            </p>
          </div>

          <form
            className="auth-form"
            onSubmit={handleDeleteSubmit(onDeleteAccountSubmit)}
          >
            <FormField
              error={deleteErrors.username?.message}
              hint="Example: grace_hopper"
              htmlFor="delete_username"
              label="Username"
            >
              <Input
                autoComplete="username"
                hasError={Boolean(deleteErrors.username)}
                id="delete_username"
                placeholder="grace_hopper"
                {...registerDeleteField("username")}
              />
            </FormField>

            <FormField
              error={deleteErrors.email?.message}
              hint="Example: grace_hopper@myna.com"
              htmlFor="delete_email"
              label="Generated email"
            >
              <Input
                autoComplete="email"
                hasError={Boolean(deleteErrors.email)}
                id="delete_email"
                placeholder="grace_hopper@myna.com"
                type="email"
                {...registerDeleteField("email")}
              />
            </FormField>

            <FormField
              error={deleteErrors.contact_number?.message}
              hint="Exactly 10 digits."
              htmlFor="delete_contact_number"
              label="Contact number"
            >
              <Input
                autoComplete="tel"
                hasError={Boolean(deleteErrors.contact_number)}
                id="delete_contact_number"
                inputMode="numeric"
                placeholder="7467449164"
                {...registerDeleteField("contact_number")}
              />
            </FormField>

            <FormField
              error={deleteErrors.current_password?.message}
              htmlFor="delete_current_password"
              label="Current password"
            >
              <Input
                autoComplete="current-password"
                hasError={Boolean(deleteErrors.current_password)}
                id="delete_current_password"
                placeholder="Current password"
                type="password"
                {...registerDeleteField("current_password")}
              />
            </FormField>

            <FormField
              error={deleteErrors.confirmation_text?.message}
              hint="Type DELETE MY ACCOUNT exactly."
              htmlFor="confirmation_text"
              label="Confirmation text"
            >
              <Input
                autoComplete="off"
                hasError={Boolean(deleteErrors.confirmation_text)}
                id="confirmation_text"
                placeholder="DELETE MY ACCOUNT"
                {...registerDeleteField("confirmation_text")}
              />
            </FormField>

            {deleteServerMessage ? (
              <div className="auth-error" role="alert">
                {deleteServerMessage}
              </div>
            ) : null}

            <Button disabled={isDeleteBusy} fullWidth type="submit">
              {isDeleteBusy ? "Deleting account..." : "Delete account"}
            </Button>
          </form>
        </div>

        <div className="hero-actions">
          <Link className="button ghost" to="/app">
            Back to app
          </Link>

          <LogoutButton />
        </div>
      </section>
    </main>
  );
}