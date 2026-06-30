import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";

import { Button, Dialog, Input } from "@/components/ui";

import { useContacts } from "./use-contacts";

import {
  saveContactSchema,
  type SaveContactFormValues,
} from "./validation/save-contact-schema";

import type {
  SearchContactResponse,
} from "./contacts-types";

interface SaveContactDialogProps {
  open: boolean;

  contact: SearchContactResponse | null;

  onClose(): void;

  onSuccess(): void;
}

export function SaveContactDialog({
  open,
  contact,
  onClose,
  onSuccess,
}: SaveContactDialogProps) {
  const { add } = useContacts();

  const [saveError, setSaveError] =
    useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<SaveContactFormValues>({
    resolver: zodResolver(
      saveContactSchema,
    ),

    defaultValues: {
      saved_name: "",
    },
  });

  useEffect(() => {
    if (!contact) {
      reset({
        saved_name: "",
      });
      return;
    }

    reset({
      saved_name: contact.full_name,
    });
  }, [contact, reset]);

  async function onSubmit(
    data: SaveContactFormValues,
  ) {
    if (!contact) {
      return;
    }

    setSaveError("");

    try {
      await add({
        contact_number: Number(
          contact.contact_number,
        ),
        saved_name: data.saved_name,
      });

      onSuccess();

      onClose();
    } catch (error) {
      console.error(
        "Save contact failed:",
        error,
      );

      setSaveError(
        error instanceof Error
          ? error.message
          : "Unable to save contact.",
      );
    }
  }

  return (
    <Dialog
      open={open}
      title="Save Contact"
      onClose={onClose}
    >
      {saveError && (
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

          <span>{saveError}</span>
        </div>
      )}

      {contact && (
        <form
          onSubmit={handleSubmit(
            onSubmit,
          )}
          noValidate
        >
          <Input
            label="Contact Number"
            value={String(
              contact.contact_number,
            )}
            disabled
            fullWidth
          />

          <div
            style={{
              marginTop:
                "var(--spacing-md)",
            }}
          >
            <Input
              label="Saved Name"
              placeholder="Enter a name for this contact"
              fullWidth
              error={
                errors.saved_name
                  ?.message
              }
              {...register(
                "saved_name",
              )}
            />
          </div>

          <div
            style={{
              display: "flex",
              gap: "1rem",
              marginTop:
                "var(--spacing-xl)",
            }}
          >
            <Button
              type="button"
              variant="secondary"
              fullWidth
              onClick={onClose}
            >
              Cancel
            </Button>

            <Button
              type="submit"
              fullWidth
              loading={
                isSubmitting
              }
            >
              Save Contact
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
