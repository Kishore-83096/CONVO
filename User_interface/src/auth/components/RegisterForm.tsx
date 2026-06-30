import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";

import { useAuth } from "@/auth/use-auth";
import {
  registerSchema,
  type RegisterFormValues,
} from "@/auth/validation/register-schema";
import { Button, Input } from "@/components/ui";

import { AuthLogo } from "./AuthLogo";

export function RegisterForm() {
  const navigate = useNavigate();

  const {
    register: registerUser,
  } = useAuth();

  const [registerError, setRegisterError] =
    useState("");

  const {
    register,
    handleSubmit,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),

    defaultValues: {
      full_name: "",
      username: "",
      password: "",
      confirm_password: "",
    },
  });

  async function onSubmit(
    data: RegisterFormValues,
  ) {
    setRegisterError("");

    try {
      await registerUser(data);

      navigate("/login", {
        replace: true,
        state: {
          username: data.username
            .replace(/^@/, "")
            .toLowerCase(),
          registrationSuccess: true,
        },
      });
    } catch (error) {
      console.error(
        "Registration failed:",
        error,
      );

      setRegisterError(
        error instanceof Error
          ? error.message
          : "Unable to create account.",
      );
    }
  }

  return (
    <>
      <AuthLogo />

      {registerError && (
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

          <span>{registerError}</span>
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
          <Input
            label="Full Name"
            placeholder="Enter your full name"
            fullWidth
            autoComplete="name"
            error={
              errors.full_name?.message
            }
            {...register("full_name")}
          />

          <div
            style={{
              marginTop:
                "var(--spacing-md)",
            }}
          >
            <Input
              label="Username"
              placeholder="Choose a username"
              fullWidth
              autoComplete="username"
              helperText="Only lowercase letters, numbers, and underscores are allowed."
              error={
                errors.username?.message
              }
              {...register("username")}
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
              placeholder="Create a password"
              fullWidth
              autoComplete="new-password"
              helperText="Password must be between 8 and 128 characters."
              error={
                errors.password?.message
              }
              {...register("password")}
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
              label="Confirm Password"
              placeholder="Confirm your password"
              fullWidth
              autoComplete="new-password"
              error={
                errors.confirm_password
                  ?.message
              }
              {...register(
                "confirm_password",
              )}
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
              Create Account
            </Button>
          </div>
        </fieldset>

        <p className="auth-form__footer">
          Already have an account?{" "}
          <Link
            to="/login"
            className="auth-form__link"
          >
            Sign In
          </Link>
        </p>
      </form>
    </>
  );
}
