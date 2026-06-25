import { useState, type FormEvent } from "react"

import {
  createBasicProfile,
  deleteBasicProfile,
  updateBasicProfile,
} from "@/app/convo/profile/profile.api"
import type { BasicProfileInput, CompleteProfile } from "@/app/convo/profile/profile.types"

interface UpdateProfilePageProps {
  accessToken: string
  profile: CompleteProfile
  onUpdated: () => void
}

function emptyToNull(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim()
  return text.length ? text : null
}

function UpdateProfilePage({
  accessToken,
  profile,
  onUpdated,
}: UpdateProfilePageProps) {
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const basicData = profile.basic_data

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const request: BasicProfileInput = {
      bio: emptyToNull(formData.get("bio")),
      date_of_birth: emptyToNull(formData.get("date_of_birth")),
      gender: emptyToNull(formData.get("gender")),
      occupation: emptyToNull(formData.get("occupation")),
      website: emptyToNull(formData.get("website")),
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      if (basicData) {
        await updateBasicProfile(request, accessToken)
      } else {
        await createBasicProfile(request, accessToken)
      }

      setMessage("Profile updated.")
      onUpdated()
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to update profile.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!basicData) {
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await deleteBasicProfile(accessToken)
      setMessage("Basic profile deleted.")
      onUpdated()
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete basic profile.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="workspace-panel active">
      <form className="flat-form" onSubmit={handleSubmit}>
        <div className="form-field form-field-wide">
          <label htmlFor="bio">Bio</label>
          <textarea id="bio" name="bio" defaultValue={basicData?.bio ?? ""} />
        </div>
        <div className="form-field">
          <label htmlFor="date_of_birth">Date of birth</label>
          <input
            id="date_of_birth"
            name="date_of_birth"
            type="date"
            defaultValue={basicData?.date_of_birth ?? ""}
          />
        </div>
        <div className="form-field">
          <label htmlFor="gender">Gender</label>
          <input id="gender" name="gender" defaultValue={basicData?.gender ?? ""} />
        </div>
        <div className="form-field">
          <label htmlFor="occupation">Occupation</label>
          <input
            id="occupation"
            name="occupation"
            maxLength={100}
            defaultValue={basicData?.occupation ?? ""}
          />
        </div>
        <div className="form-field">
          <label htmlFor="website">Website</label>
          <input
            id="website"
            name="website"
            type="url"
            defaultValue={basicData?.website ?? ""}
          />
        </div>
        <div className="form-actions form-field-wide">
          <button className="secondary-action-button" type="reset">
            Reset
          </button>
          {basicData ? (
            <button
              className="secondary-action-button"
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleDelete()}
            >
              Delete Basic Data
            </button>
          ) : null}
          <button
            className="primary-action-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Updating..." : "Update Profile"}
          </button>
        </div>
      </form>
      {message ? <p className="contact-message">{message}</p> : null}
      {error ? (
        <p className="contact-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}

export default UpdateProfilePage
