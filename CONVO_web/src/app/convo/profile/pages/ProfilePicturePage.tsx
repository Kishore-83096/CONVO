import { useEffect, useState, type ChangeEvent } from "react"

import {
  deleteProfilePicture,
  uploadProfilePicture,
} from "@/app/convo/profile/profile.api"
import type { CompleteProfile } from "@/app/convo/profile/profile.types"
import ConfirmActionModal from "@/app/convo/layout/components/ConfirmActionModal"
import ImageCropper from "@/app/convo/shared/components/ImageCropper"

interface ProfilePicturePageProps {
  accessToken: string
  profile: CompleteProfile
  onUpdated: () => void
}

function CroppedPreview({ file }: { file: File }) {
  const [previewUrl, setPreviewUrl] = useState("")

  useEffect(() => {
    const nextPreviewUrl = URL.createObjectURL(file)
    setPreviewUrl(nextPreviewUrl)

    return () => URL.revokeObjectURL(nextPreviewUrl)
  }, [file])

  return (
    <div className="convo-cropped-preview">
      {previewUrl ? <img src={previewUrl} alt="" /> : null}
      <span>{file.name}</span>
    </div>
  )
}

function ProfilePicturePage({
  accessToken,
  profile,
  onUpdated,
}: ProfilePicturePageProps) {
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [croppedFile, setCroppedFile] = useState<File | null>(null)
  const picture = profile.profile_picture

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const image = event.target.files?.[0] ?? null

    setMessage("")
    setError("")
    setCroppedFile(null)

    if (!image) {
      setSelectedFile(null)
      return
    }

    if (!["image/jpeg", "image/png"].includes(image.type)) {
      setError("Choose a JPEG or PNG image.")
      setSelectedFile(null)
      return
    }

    setSelectedFile(image)
  }

  const handleUpload = async () => {
    if (!croppedFile) {
      setError("Crop the image before uploading.")
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await uploadProfilePicture(croppedFile, Boolean(picture), accessToken)
      setMessage(picture ? "Profile picture replaced." : "Profile picture uploaded.")
      setSelectedFile(null)
      setCroppedFile(null)
      onUpdated()
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload profile picture.",
      )
    } finally {
      setIsSubmitting(false)
      setIsDeleteConfirmOpen(false)
    }
  }

  const handleDelete = async () => {
    if (!picture) {
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await deleteProfilePicture(accessToken)
      setMessage("Profile picture deleted.")
      setSelectedFile(null)
      setCroppedFile(null)
      onUpdated()
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete profile picture.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="workspace-panel active">
      <div className="flat-profile-hero">
        {picture ? (
          <img className="profile-page-avatar" src={picture.url} alt="" />
        ) : (
          <span className="profile-page-avatar">
            {profile.identity.full_name.charAt(0).toUpperCase()}
          </span>
        )}
        <div>
          <h3>{picture ? "Profile picture" : "No profile picture"}</h3>
          <p>
            {picture
              ? `${picture.format ?? "image"} - ${picture.bytes ?? 0} bytes`
              : "JPEG or PNG, up to 5 MB"}
          </p>
        </div>
      </div>

      <div className="flat-form single-column-form">
        <div className="form-field">
          <label htmlFor="image">Image file</label>
          <input
            id="image"
            name="image"
            type="file"
            accept="image/jpeg,image/png"
            onChange={handleFileChange}
          />
        </div>

        {selectedFile ? (
          <ImageCropper
            file={selectedFile}
            outputFileName="profile-picture.jpg"
            onCancel={() => {
              setSelectedFile(null)
              setCroppedFile(null)
            }}
            onCrop={(file) => {
              setCroppedFile(file)
              setMessage("Crop ready to upload.")
              setError("")
            }}
          />
        ) : null}

        {croppedFile ? <CroppedPreview file={croppedFile} /> : null}

        <div className="form-actions">
          {picture ? (
            <button
              className="secondary-action-button"
              type="button"
              disabled={isSubmitting}
              onClick={() => setIsDeleteConfirmOpen(true)}
            >
              Delete Picture
            </button>
          ) : null}
          <button
            className="primary-action-button"
            type="button"
            disabled={isSubmitting || !croppedFile}
            onClick={() => void handleUpload()}
          >
            {isSubmitting
              ? "Uploading..."
              : picture
                ? "Replace Picture"
                : "Upload Picture"}
          </button>
        </div>
      </div>
      {message ? <p className="convo-profile-message">{message}</p> : null}
      {error ? (
        <p className="convo-profile-error" role="alert">
          {error}
        </p>
      ) : null}

      <ConfirmActionModal
        confirmLabel="Delete picture"
        description="This will remove your current profile picture from CONVO. You can upload a new one later."
        isBusy={isSubmitting}
        isOpen={isDeleteConfirmOpen}
        title="Delete profile picture?"
        tone="danger"
        onCancel={() => setIsDeleteConfirmOpen(false)}
        onConfirm={() => void handleDelete()}
      />
    </section>
  )
}

export default ProfilePicturePage
