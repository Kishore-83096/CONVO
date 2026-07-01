import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import { useResetPassword } from "../../auth/hooks";
import { resetPasswordSchema } from "../../auth/schemas";
import type {
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

export function ResetPasswordPanel() {
  const [serverMessage, setServerMessage] = useState("");

  const navigate = useNavigate();
  const { user, clearSession } = useAuth();
  const resetPasswordMutation = useResetPassword();

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
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

  async function redirectMissingSession() {
    await clearSession();

    navigate("/login", {
      replace: true,
      state: {
        message: "Your session was not found. Please login again.",
      },
    });
  }

  async function onSubmit(values: ResetPasswordFormValues) {
    setServerMessage("");

    if (!user) {
      setServerMessage("Your session was not found. Please login again.");
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
      reset();
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

    setServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of resetPasswordFieldNames) {
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

  const isBusy = isSubmitting || resetPasswordMutation.isPending;

  return (
    <section className="settings-section">
      <div>
        <h2>Reset password</h2>
        <p>
          Type your account details manually. The saved session only confirms
          that you are logged in.
        </p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit(onSubmit)}>
        <FormField
          error={errors.username?.message}
          hint="Example: grace_hopper"
          htmlFor="reset_username"
          label="Username"
        >
          <Input
            autoComplete="username"
            hasError={Boolean(errors.username)}
            id="reset_username"
            placeholder="grace_hopper"
            {...register("username")}
          />
        </FormField>

        <FormField
          error={errors.email?.message}
          hint="Example: grace_hopper@myna.com"
          htmlFor="reset_email"
          label="Generated email"
        >
          <Input
            autoComplete="email"
            hasError={Boolean(errors.email)}
            id="reset_email"
            placeholder="grace_hopper@myna.com"
            type="email"
            {...register("email")}
          />
        </FormField>

        <FormField
          error={errors.contact_number?.message}
          hint="Exactly 10 digits."
          htmlFor="reset_contact_number"
          label="Contact number"
        >
          <Input
            autoComplete="tel"
            hasError={Boolean(errors.contact_number)}
            id="reset_contact_number"
            inputMode="numeric"
            placeholder="7467449164"
            {...register("contact_number")}
          />
        </FormField>

        <FormField
          error={errors.current_password?.message}
          htmlFor="reset_current_password"
          label="Current password"
        >
          <Input
            autoComplete="current-password"
            hasError={Boolean(errors.current_password)}
            id="reset_current_password"
            placeholder="Current password"
            type="password"
            {...register("current_password")}
          />
        </FormField>

        <FormField
          error={errors.new_password?.message}
          hint="Use 8-128 characters. Do not reuse your current password."
          htmlFor="new_password"
          label="New password"
        >
          <Input
            autoComplete="new-password"
            hasError={Boolean(errors.new_password)}
            id="new_password"
            placeholder="NewStrongPass123!"
            type="password"
            {...register("new_password")}
          />
        </FormField>

        <FormField
          error={errors.confirm_new_password?.message}
          htmlFor="confirm_new_password"
          label="Confirm new password"
        >
          <Input
            autoComplete="new-password"
            hasError={Boolean(errors.confirm_new_password)}
            id="confirm_new_password"
            placeholder="NewStrongPass123!"
            type="password"
            {...register("confirm_new_password")}
          />
        </FormField>

        {serverMessage ? (
          <div className="auth-error" role="alert">
            {serverMessage}
          </div>
        ) : null}

        <Button disabled={isBusy} fullWidth type="submit">
          {isBusy ? "Resetting password..." : "Reset password"}
        </Button>
      </form>
    </section>
  );
}
