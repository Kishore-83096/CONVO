import {
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  type FormEvent,
  useState,
} from "react";
import {
  useNavigate,
} from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { isApiError } from "@/api/api-errors";
import { useAuth } from "@/auth/use-auth";
import { Button, Input } from "@/components/ui";
import { DeviceSettingsPage } from "@/devices/DeviceSettingsPage";
import { RecoveryDashboard } from "@/recovery/RecoveryDashboard";

type ResetPasswordForm = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
  new_password: string;
  confirm_new_password: string;
};

type DeleteAccountForm = {
  username: string;
  email: string;
  contact_number: string;
  current_password: string;
};

const emptyResetPasswordForm: ResetPasswordForm = {
  username: "",
  email: "",
  contact_number: "",
  current_password: "",
  new_password: "",
  confirm_new_password: "",
};

const emptyDeleteAccountForm: DeleteAccountForm = {
  username: "",
  email: "",
  contact_number: "",
  current_password: "",
};

export function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const {
    resetPassword,
    deleteAccount,
  } = useAuth();

  const [resetForm, setResetForm] =
    useState<ResetPasswordForm>(emptyResetPasswordForm);
  const [deleteForm, setDeleteForm] =
    useState<DeleteAccountForm>(emptyDeleteAccountForm);
  const [resetError, setResetError] =
    useState<string | null>(null);
  const [deleteError, setDeleteError] =
    useState<string | null>(null);
  const [resetFieldErrors, setResetFieldErrors] =
    useState<Record<string, string>>({});
  const [deleteFieldErrors, setDeleteFieldErrors] =
    useState<Record<string, string>>({});
  const [isResetting, setIsResetting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  function updateResetField(
    field: keyof ResetPasswordForm,
    value: string,
  ) {
    setResetForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateDeleteField(
    field: keyof DeleteAccountForm,
    value: string,
  ) {
    setDeleteForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleResetPassword(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setResetError(null);
    setResetFieldErrors({});

    const validationErrors =
      validateResetPassword(resetForm);

    if (Object.keys(validationErrors).length > 0) {
      setResetFieldErrors(validationErrors);
      return;
    }

    setIsResetting(true);

    try {
      await resetPassword(trimResetForm(resetForm));
      queryClient.clear();

      navigate("/login", {
        replace: true,
        state: {
          sessionNotice:
            "Password changed. Please sign in again.",
        },
      });
    } catch (error) {
      setResetError(errorMessage(error));
      setResetFieldErrors(fieldErrors(error));
    } finally {
      setIsResetting(false);
    }
  }

  async function handleDeleteAccount(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setDeleteError(null);
    setDeleteFieldErrors({});

    const validationErrors =
      validateDeleteAccount(deleteForm);

    if (Object.keys(validationErrors).length > 0) {
      setDeleteFieldErrors(validationErrors);
      return;
    }

    setIsDeleting(true);

    try {
      await deleteAccount(trimDeleteForm(deleteForm));
      queryClient.clear();

      navigate("/login", {
        replace: true,
        state: {
          sessionNotice:
            "Account deleted. Local session data has been cleared.",
        },
      });
    } catch (error) {
      setDeleteError(errorMessage(error));
      setDeleteFieldErrors(fieldErrors(error));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <section className="workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <span className="section-kicker">Account</span>
            <h1>Settings</h1>
          </div>
        </div>
      </header>
      <div className="workspace-content">
        <div className="settings-security-grid">
          <DeviceSettingsPage />
          <RecoveryDashboard />
        </div>

        <div className="settings-grid">
          <section className="settings-panel">
            <div className="settings-panel__header">
              <ShieldCheck size={20} aria-hidden="true" />
              <div>
                <h2>Password reset</h2>
                <p>
                  Change your password after confirming your account details.
                </p>
              </div>
            </div>

            {resetError && (
              <div className="settings-error" role="alert">
                {resetError}
              </div>
            )}

            <form
              className="settings-form"
              onSubmit={handleResetPassword}
              noValidate
            >
              <Input
                label="Username"
                value={resetForm.username}
                onChange={(event) =>
                  updateResetField("username", event.target.value)
                }
                autoComplete="username"
                error={resetFieldErrors.username}
                fullWidth
                required
              />

              <Input
                label="Email"
                type="email"
                value={resetForm.email}
                onChange={(event) =>
                  updateResetField("email", event.target.value)
                }
                autoComplete="email"
                error={resetFieldErrors.email}
                fullWidth
                required
              />

              <Input
                label="Contact number"
                value={resetForm.contact_number}
                onChange={(event) =>
                  updateResetField(
                    "contact_number",
                    event.target.value,
                  )
                }
                autoComplete="tel"
                inputMode="tel"
                error={resetFieldErrors.contact_number}
                fullWidth
                required
              />

              <Input
                label="Current password"
                type="password"
                value={resetForm.current_password}
                onChange={(event) =>
                  updateResetField(
                    "current_password",
                    event.target.value,
                  )
                }
                autoComplete="current-password"
                error={resetFieldErrors.current_password}
                fullWidth
                required
              />

              <Input
                label="New password"
                type="password"
                value={resetForm.new_password}
                onChange={(event) =>
                  updateResetField(
                    "new_password",
                    event.target.value,
                  )
                }
                autoComplete="new-password"
                error={resetFieldErrors.new_password}
                fullWidth
                required
              />

              <Input
                label="Confirm new password"
                type="password"
                value={resetForm.confirm_new_password}
                onChange={(event) =>
                  updateResetField(
                    "confirm_new_password",
                    event.target.value,
                  )
                }
                autoComplete="new-password"
                error={resetFieldErrors.confirm_new_password}
                fullWidth
                required
              />

              <div className="settings-actions">
                <Button
                  type="submit"
                  loading={isResetting}
                >
                  Change Password
                </Button>
              </div>
            </form>
          </section>

          <section className="settings-panel settings-panel--danger">
            <div className="settings-panel__header">
              <Trash2 size={20} aria-hidden="true" />
              <div>
                <h2>Delete account</h2>
                <p>
                  Permanently remove your account after confirming your identity.
                </p>
              </div>
            </div>

            {deleteError && (
              <div className="settings-error" role="alert">
                {deleteError}
              </div>
            )}

            <form
              className="settings-form"
              onSubmit={handleDeleteAccount}
              noValidate
            >
              <Input
                label="Username"
                value={deleteForm.username}
                onChange={(event) =>
                  updateDeleteField("username", event.target.value)
                }
                autoComplete="username"
                error={deleteFieldErrors.username}
                fullWidth
                required
              />

              <Input
                label="Email"
                type="email"
                value={deleteForm.email}
                onChange={(event) =>
                  updateDeleteField("email", event.target.value)
                }
                autoComplete="email"
                error={deleteFieldErrors.email}
                fullWidth
                required
              />

              <Input
                label="Contact number"
                value={deleteForm.contact_number}
                onChange={(event) =>
                  updateDeleteField(
                    "contact_number",
                    event.target.value,
                  )
                }
                autoComplete="tel"
                inputMode="tel"
                error={deleteFieldErrors.contact_number}
                fullWidth
                required
              />

              <Input
                label="Current password"
                type="password"
                value={deleteForm.current_password}
                onChange={(event) =>
                  updateDeleteField(
                    "current_password",
                    event.target.value,
                  )
                }
                autoComplete="current-password"
                error={deleteFieldErrors.current_password}
                fullWidth
                required
              />

              <div className="settings-actions">
                <Button
                  type="submit"
                  variant="danger"
                  loading={isDeleting}
                >
                  Delete Account
                </Button>
              </div>
            </form>
          </section>
        </div>
      </div>
    </section>
  );
}

function validateResetPassword(
  form: ResetPasswordForm,
): Record<string, string> {
  const errors = requiredErrors(form);

  if (
    form.new_password &&
    form.confirm_new_password &&
    form.new_password !== form.confirm_new_password
  ) {
    errors.confirm_new_password =
      "New password confirmation must match.";
  }

  return errors;
}

function validateDeleteAccount(
  form: DeleteAccountForm,
): Record<string, string> {
  return requiredErrors(form);
}

function requiredErrors(
  form: Record<string, string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(form)
      .filter(([, value]) => value.trim().length === 0)
      .map(([field]) => [field, "This field is required."]),
  );
}

function trimResetForm(
  form: ResetPasswordForm,
): ResetPasswordForm {
  return {
    username: form.username.trim(),
    email: form.email.trim(),
    contact_number: form.contact_number.trim(),
    current_password: form.current_password,
    new_password: form.new_password,
    confirm_new_password: form.confirm_new_password,
  };
}

function trimDeleteForm(
  form: DeleteAccountForm,
): DeleteAccountForm {
  return {
    username: form.username.trim(),
    email: form.email.trim(),
    contact_number: form.contact_number.trim(),
    current_password: form.current_password,
  };
}

function fieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) {
    return {};
  }

  const fields = [
    "username",
    "email",
    "contact_number",
    "current_password",
    "new_password",
    "confirm_new_password",
  ];

  return Object.fromEntries(
    fields
      .map((field) => [field, error.getFieldError(field)])
      .filter((entry): entry is [string, string] =>
        typeof entry[1] === "string",
      ),
  );
}

function errorMessage(error: unknown): string {
  if (isApiError(error) || error instanceof Error) {
    return error.message;
  }

  return "Account request failed.";
}
