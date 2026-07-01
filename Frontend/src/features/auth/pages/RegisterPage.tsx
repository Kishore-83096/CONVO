import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import { PublicLayout } from "../../../shared/ui/PublicLayout";
import { useRegisterUser } from "../hooks";
import { registerSchema, type RegisterFormValues } from "../schemas";
import type { RegisterFieldName } from "../types";

const registerFieldNames: RegisterFieldName[] = [
  "full_name",
  "username",
  "password",
  "confirm_password",
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

export function RegisterPage() {
  const [serverMessage, setServerMessage] = useState("");

  const navigate = useNavigate();
  const registerMutation = useRegisterUser();

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      full_name: "",
      username: "",
      password: "",
      confirm_password: "",
    },
  });

  async function onSubmit(values: RegisterFormValues) {
    setServerMessage("");

    const result = await registerMutation.mutateAsync(values);

    if (result.ok) {
      reset({
        full_name: "",
        username: "",
        password: "",
        confirm_password: "",
      });

      navigate("/login", {
        replace: true,
        state: {
          registrationSuccess: true,
          registeredUser: result.data,
        },
      });

      return;
    }

    setServerMessage(result.message);

    if (isErrorMap(result.errors)) {
      for (const fieldName of registerFieldNames) {
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

  const isBusy = isSubmitting || registerMutation.isPending;

  return (
    <PublicLayout>
      <section className="auth-public-page">
        <div className="auth-card">
          <p className="eyebrow">Sprint 1 · Phase 1.1</p>

          <h1>Create your account</h1>

          <p>
            Register your Secure Chat identity. The backend will generate your
            email and unique 10-digit contact number after successful
            registration.
          </p>

          <form className="auth-form" onSubmit={handleSubmit(onSubmit)}>
            <FormField
              error={errors.full_name?.message}
              htmlFor="full_name"
              label="Full name"
            >
              <Input
                autoComplete="name"
                hasError={Boolean(errors.full_name)}
                id="full_name"
                placeholder="Grace Hopper"
                {...register("full_name")}
              />
            </FormField>

            <FormField
              error={errors.username?.message}
              hint="3–30 characters. Use lowercase letters, numbers, and underscores only. You can type @, but it will be removed before submit."
              htmlFor="username"
              label="Username"
            >
              <Input
                autoComplete="username"
                hasError={Boolean(errors.username)}
                id="username"
                placeholder="grace_hopper"
                {...register("username")}
              />
            </FormField>

            <FormField
              error={errors.password?.message}
              hint="Use 8–128 characters. Add uppercase, lowercase, numbers, and symbols for stronger security."
              htmlFor="password"
              label="Password"
            >
              <Input
                autoComplete="new-password"
                hasError={Boolean(errors.password)}
                id="password"
                placeholder="StrongPass123!"
                type="password"
                {...register("password")}
              />
            </FormField>

            <FormField
              error={errors.confirm_password?.message}
              htmlFor="confirm_password"
              label="Confirm password"
            >
              <Input
                autoComplete="new-password"
                hasError={Boolean(errors.confirm_password)}
                id="confirm_password"
                placeholder="StrongPass123!"
                type="password"
                {...register("confirm_password")}
              />
            </FormField>

            {serverMessage ? (
              <div className="auth-error" role="alert">
                {serverMessage}
              </div>
            ) : null}

            <Button disabled={isBusy} fullWidth type="submit">
              {isBusy ? "Creating account..." : "Create account"}
            </Button>
          </form>

          <div className="hero-actions">
            <Link className="button secondary" to="/login">
              Already have account?
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
