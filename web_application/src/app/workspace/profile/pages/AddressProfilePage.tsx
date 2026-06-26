import { useState, type FormEvent } from "react"

import {
  createAddress,
  deleteAddress,
  updateAddress,
} from "@/app/workspace/profile/profile.api"
import type {
  AddressCreateInput,
  CompleteProfile,
} from "@/app/workspace/profile/profile.types"

interface AddressProfilePageProps {
  accessToken: string
  profile: CompleteProfile
  onUpdated: () => void
}

function textValue(value: FormDataEntryValue | null) {
  return String(value ?? "").trim()
}

function optionalText(value: FormDataEntryValue | null) {
  const text = textValue(value)
  return text.length ? text : null
}

function AddressProfilePage({
  accessToken,
  profile,
  onUpdated,
}: AddressProfilePageProps) {
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const address = profile.address

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const request: AddressCreateInput = {
      address_line_1: textValue(formData.get("address_line_1")),
      address_line_2: optionalText(formData.get("address_line_2")),
      city: textValue(formData.get("city")),
      state: optionalText(formData.get("state")),
      postal_code: optionalText(formData.get("postal_code")),
      country: textValue(formData.get("country")),
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      if (address) {
        await updateAddress(request, accessToken)
      } else {
        await createAddress(request, accessToken)
      }

      setMessage("Address saved.")
      onUpdated()
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to save address.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!address) {
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await deleteAddress(accessToken)
      setMessage("Address deleted.")
      onUpdated()
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete address.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="workspace-panel active">
      <form className="flat-form" onSubmit={handleSubmit}>
        <div className="form-field form-field-wide">
          <label htmlFor="address_line_1">Address line 1</label>
          <input
            id="address_line_1"
            name="address_line_1"
            defaultValue={address?.address_line_1 ?? ""}
            required
          />
        </div>
        <div className="form-field form-field-wide">
          <label htmlFor="address_line_2">Address line 2</label>
          <input
            id="address_line_2"
            name="address_line_2"
            defaultValue={address?.address_line_2 ?? ""}
          />
        </div>
        <div className="form-field">
          <label htmlFor="city">City</label>
          <input id="city" name="city" defaultValue={address?.city ?? ""} required />
        </div>
        <div className="form-field">
          <label htmlFor="state">State</label>
          <input id="state" name="state" defaultValue={address?.state ?? ""} />
        </div>
        <div className="form-field">
          <label htmlFor="postal_code">Postal code</label>
          <input
            id="postal_code"
            name="postal_code"
            defaultValue={address?.postal_code ?? ""}
          />
        </div>
        <div className="form-field">
          <label htmlFor="country">Country</label>
          <input
            id="country"
            name="country"
            defaultValue={address?.country ?? ""}
            required
          />
        </div>
        <div className="form-actions form-field-wide">
          <button className="secondary-action-button" type="reset">
            Reset
          </button>
          {address ? (
            <button
              className="secondary-action-button"
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleDelete()}
            >
              Delete Address
            </button>
          ) : null}
          <button
            className="primary-action-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : "Save Address"}
          </button>
        </div>
      </form>
      {message ? <p className="profile-message">{message}</p> : null}
      {error ? (
        <p className="profile-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}

export default AddressProfilePage
