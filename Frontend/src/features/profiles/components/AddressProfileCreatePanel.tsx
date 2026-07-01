import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  addressProfileCreateSchema,
  type AddressProfileCreateFormValues,
} from "../schemas";
import { useCreateMyProfileAddress } from "../hooks";

type AddressProfileCreatePanelProps = {
  onCreated?: () => void;
};

function toPayload(values: AddressProfileCreateFormValues) {
  return {
    address_line_1: values.address_line_1.trim(),
    city: values.city.trim(),
    country: values.country.trim(),
    address_line_2: values.address_line_2.trim() || undefined,
    state: values.state.trim() || undefined,
    postal_code: values.postal_code.trim() || undefined,
  };
}

export function AddressProfileCreatePanel({
  onCreated,
}: AddressProfileCreatePanelProps = {}) {
  const createAddressProfile = useCreateMyProfileAddress();

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<AddressProfileCreateFormValues>({
    resolver: zodResolver(addressProfileCreateSchema),
    defaultValues: {
      address_line_1: "",
      address_line_2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "",
    },
  });

  async function onSubmit(values: AddressProfileCreateFormValues) {
    const result = await createAddressProfile.mutateAsync(toPayload(values));

    if (result.ok) {
      reset();
      onCreated?.();
    }
  }

  const isDisabled = isSubmitting || createAddressProfile.isPending;

  return (
    <section
      className="account-settings-panel"
      aria-label="Create address profile"
    >
      <div className="section-heading">
        <p className="eyebrow">Phase 2.7</p>
        <h2>Create Address Profile</h2>
        <p>
          This form creates your address profile using POST
          /profiles/me/address. Edit and delete are not included in this phase.
        </p>
      </div>

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

        {createAddressProfile.data && !createAddressProfile.data.ok ? (
          <div className="auth-error" role="alert">
            {createAddressProfile.data.message}
          </div>
        ) : null}

        {createAddressProfile.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Address profile created.</strong>
            <p>The read-only address section should refresh automatically.</p>
          </div>
        ) : null}

        {createAddressProfile.isError ? (
          <div className="auth-error" role="alert">
            Address profile request failed before the server returned a
            response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? "Creating..." : "Create address profile"}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={() => reset()}
            type="button"
            variant="secondary"
          >
            Clear form
          </Button>
        </div>
      </form>
    </section>
  );
}
