import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  addressProfileUpdateSchema,
  type AddressProfileUpdateFormValues,
} from "../schemas";
import { useMyProfileAddress, useUpdateMyProfileAddress } from "../hooks";
import type { ProfileAddress } from "../types";

type AddressProfileUpdatePanelProps = {
  initialAddressProfile?: ProfileAddress | null;
  onUpdated?: () => void;
};

function toPayload(values: AddressProfileUpdateFormValues) {
  return {
    address_line_1: values.address_line_1.trim() || undefined,
    address_line_2: values.address_line_2.trim() || undefined,
    city: values.city.trim() || undefined,
    state: values.state.trim() || undefined,
    postal_code: values.postal_code.trim() || undefined,
    country: values.country.trim() || undefined,
  };
}

export function AddressProfileUpdatePanel({
  initialAddressProfile,
  onUpdated,
}: AddressProfileUpdatePanelProps = {}) {
  const addressProfileQuery = useMyProfileAddress();
  const updateAddressProfile = useUpdateMyProfileAddress();

  const addressProfileResult = addressProfileQuery.data;
  const queriedAddressProfile = addressProfileResult?.ok
    ? addressProfileResult.data
    : undefined;
  const addressProfile = initialAddressProfile ?? queriedAddressProfile;

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<AddressProfileUpdateFormValues>({
    resolver: zodResolver(addressProfileUpdateSchema),
    defaultValues: {
      address_line_1: "",
      address_line_2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "",
    },
  });

  useEffect(() => {
    if (!addressProfile) {
      return;
    }

    reset({
      address_line_1: addressProfile.address_line_1 ?? "",
      address_line_2: addressProfile.address_line_2 ?? "",
      city: addressProfile.city ?? "",
      state: addressProfile.state ?? "",
      postal_code: addressProfile.postal_code ?? "",
      country: addressProfile.country ?? "",
    });
  }, [addressProfile, reset]);

  async function onSubmit(values: AddressProfileUpdateFormValues) {
    const result = await updateAddressProfile.mutateAsync(toPayload(values));

    if (result.ok) {
      onUpdated?.();
    }
  }

  const isLoadingExistingProfile =
    !initialAddressProfile && addressProfileQuery.isPending;
  const isDisabled =
    isSubmitting ||
    updateAddressProfile.isPending ||
    isLoadingExistingProfile;

  return (
    <section
      className="account-settings-panel"
      aria-label="Update address profile"
    >
      <div className="section-heading">
        <p className="eyebrow">Phase 2.8</p>
        <h2>Edit Address Profile</h2>
        <p>
          This form updates your address profile using PATCH
          /profiles/me/address. It is separate from the create form.
        </p>
      </div>

      {isLoadingExistingProfile ? (
        <div className="auth-success" role="status">
          <strong>Loading existing address profile...</strong>
          <p>The edit form will fill after the address is loaded.</p>
        </div>
      ) : null}

      {!addressProfileQuery.isPending &&
      addressProfileResult &&
      !addressProfileResult.ok ? (
        <div className="auth-error" role="alert">
          {addressProfileResult.message}
        </div>
      ) : null}

      {!addressProfileQuery.isPending && addressProfileQuery.isError ? (
        <div className="auth-error" role="alert">
          Existing address profile request failed before the server returned a
          response.
        </div>
      ) : null}

      <form className="settings-form" onSubmit={handleSubmit(onSubmit)}>
        <label className="field-group">
          <span>Address line 1</span>
          <input
            {...register("address_line_1")}
            className="text-input"
            disabled={isDisabled}
            placeholder="House number, street, area"
            type="text"
          />
          {errors.address_line_1 ? (
            <small className="field-error">
              {errors.address_line_1.message}
            </small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Address line 2</span>
          <input
            {...register("address_line_2")}
            className="text-input"
            disabled={isDisabled}
            placeholder="Apartment, landmark, optional"
            type="text"
          />
          {errors.address_line_2 ? (
            <small className="field-error">
              {errors.address_line_2.message}
            </small>
          ) : null}
        </label>

        <label className="field-group">
          <span>City</span>
          <input
            {...register("city")}
            className="text-input"
            disabled={isDisabled}
            placeholder="Visakhapatnam"
            type="text"
          />
          {errors.city ? (
            <small className="field-error">{errors.city.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>State</span>
          <input
            {...register("state")}
            className="text-input"
            disabled={isDisabled}
            placeholder="Andhra Pradesh"
            type="text"
          />
          {errors.state ? (
            <small className="field-error">{errors.state.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Postal code</span>
          <input
            {...register("postal_code")}
            className="text-input"
            disabled={isDisabled}
            placeholder="530001"
            type="text"
          />
          {errors.postal_code ? (
            <small className="field-error">
              {errors.postal_code.message}
            </small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Country</span>
          <input
            {...register("country")}
            className="text-input"
            disabled={isDisabled}
            placeholder="India"
            type="text"
          />
          {errors.country ? (
            <small className="field-error">{errors.country.message}</small>
          ) : null}
        </label>

        {updateAddressProfile.data && !updateAddressProfile.data.ok ? (
          <div className="auth-error" role="alert">
            {updateAddressProfile.data.message}
          </div>
        ) : null}

        {updateAddressProfile.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Address profile updated.</strong>
            <p>The read-only address section should refresh automatically.</p>
          </div>
        ) : null}

        {updateAddressProfile.isError ? (
          <div className="auth-error" role="alert">
            Address profile update failed before the server returned a response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? "Updating..." : "Update address profile"}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={() =>
              reset({
                address_line_1: addressProfile?.address_line_1 ?? "",
                address_line_2: addressProfile?.address_line_2 ?? "",
                city: addressProfile?.city ?? "",
                state: addressProfile?.state ?? "",
                postal_code: addressProfile?.postal_code ?? "",
                country: addressProfile?.country ?? "",
              })
            }
            type="button"
            variant="secondary"
          >
            Reset to saved values
          </Button>
        </div>
      </form>
    </section>
  );
}
