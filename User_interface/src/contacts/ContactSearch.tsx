import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useState } from "react";

import { Button, Input } from "@/components/ui";

import { useContacts } from "./use-contacts";
import {
  searchContactSchema,
  type SearchContactFormValues,
} from "./validation/search-contact-schema";

import type {
  SearchContactResponse,
} from "./contacts-types";

interface ContactSearchProps {
  onSearchSuccess(
    result: SearchContactResponse,
  ): void;
}

export function ContactSearch({
  onSearchSuccess,
}: ContactSearchProps) {
  const { search } = useContacts();

  const [searchError, setSearchError] =
    useState("");

  const {
    register,
    handleSubmit,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<SearchContactFormValues>({
    resolver: zodResolver(
      searchContactSchema,
    ),

    defaultValues: {
      contact_number: "",
    },
  });

  async function onSubmit(
    data: SearchContactFormValues,
  ) {
    setSearchError("");

    try {
      const searchedContactNumber = Number(
        data.contact_number,
        );

        const result = await search({
        contact_number: searchedContactNumber,
        });

        onSearchSuccess({
        ...result,
        contact_number: searchedContactNumber,
        });

    } catch (error) {
      console.error(
        "Contact search failed:",
        error,
      );

      setSearchError(
        error instanceof Error
          ? error.message
          : "Unable to search contact.",
      );
    }
  }

  return (
    <>
      {searchError && (
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

          <span>{searchError}</span>
        </div>
      )}

      <form
        className="auth-form"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <Input
          label="Contact Number"
          placeholder="Enter 10-digit contact number"
          helperText="Enter the recipient's unique 10-digit contact number."
          fullWidth
          autoComplete="off"
          inputMode="numeric"
          maxLength={10}
          error={
            errors.contact_number
              ?.message
          }
          {...register("contact_number")}
        />

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
            Search Contact
          </Button>
        </div>
      </form>
    </>
  );
}