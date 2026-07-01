import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/useAuth";
import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import { useDeleteAccount } from "../../auth/hooks";
import { deleteAccountSchema } from "../../auth/schemas";
import type {
  DeleteAccountFieldName,
  DeleteAccountFormValues,
  DeleteAccountRequest,
} from "../../auth/types";

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

export function DeleteAccountPanel() {
  const [serverMessage, setServerMessage] = useState("");

  const navigate = useNavigate();
  const { user, clearSession } = useAuth();
  const deleteAccountMutation = useDeleteAccount();

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
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

  async function onSubmit(values: DeleteAccountFormValues) {
    setServerMessage("");

    if (!user) {
      setServerMessage("Your session was not found. Please login again.");
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
      reset();
      await clearSession();

      navigate("/login", {
        replace: true,
        state: {
          message:
            "Your account was deleted successfully. Create a new account if you want to use Secure Chat again.",
        },
      });

      return;
    }

    setServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of deleteAccountFieldNames) {
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

  const isBusy = isSubmitting || deleteAccountMutation.isPending;

  return (
    <section className="danger-zone">
      <div>
        <p className="eyebrow">Danger zone</p>
        <h2>Delete account</h2>
        <p>
          Type your account details manually before deleting. Use only a test
          account while developing because this permanently deletes the user.
        </p>
      </div>

      <form className="auth-form" onSubmit={handleSubmit(onSubmit)}>
        <FormField
          error={errors.username?.message}
          hint="Example: grace_hopper"
          htmlFor="delete_username"
          label="Username"
        >
          <Input
            autoComplete="username"
            hasError={Boolean(errors.username)}
            id="delete_username"
            placeholder="grace_hopper"
            {...register("username")}
          />
        </FormField>

        <FormField
          error={errors.email?.message}
          hint="Example: grace_hopper@myna.com"
          htmlFor="delete_email"
          label="Generated email"
        >
          <Input
            autoComplete="email"
            hasError={Boolean(errors.email)}
            id="delete_email"
            placeholder="grace_hopper@myna.com"
            type="email"
            {...register("email")}
          />
        </FormField>

        <FormField
          error={errors.contact_number?.message}
          hint="Exactly 10 digits."
          htmlFor="delete_contact_number"
          label="Contact number"
        >
          <Input
            autoComplete="tel"
            hasError={Boolean(errors.contact_number)}
            id="delete_contact_number"
            inputMode="numeric"
            placeholder="7467449164"
            {...register("contact_number")}
          />
        </FormField>

        <FormField
          error={errors.current_password?.message}
          htmlFor="delete_current_password"
          label="Current password"
        >
          <Input
            autoComplete="current-password"
            hasError={Boolean(errors.current_password)}
            id="delete_current_password"
            placeholder="Current password"
            type="password"
            {...register("current_password")}
          />
        </FormField>

        <FormField
          error={errors.confirmation_text?.message}
          hint="Type DELETE MY ACCOUNT exactly."
          htmlFor="confirmation_text"
          label="Confirmation text"
        >
          <Input
            autoComplete="off"
            hasError={Boolean(errors.confirmation_text)}
            id="confirmation_text"
            placeholder="DELETE MY ACCOUNT"
            {...register("confirmation_text")}
          />
        </FormField>

        {serverMessage ? (
          <div className="auth-error" role="alert">
            {serverMessage}
          </div>
        ) : null}

        <Button disabled={isBusy} fullWidth type="submit" variant="danger">
          {isBusy ? "Deleting account..." : "Delete account"}
        </Button>
      </form>
    </section>
  );
}
