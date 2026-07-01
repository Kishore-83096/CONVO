import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { Button } from "../../../shared/ui/Button";
import { FormModal } from "../../../shared/ui/FormModal";
import {
  useCreateMyProfilePicture,
  useMyProfile,
  useMyProfilePicture,
  useUpdateMyProfilePicture,
} from "../hooks";
import type { MyProfile, ProfileEvent, ProfilePicture } from "../types";
import { BasicProfileCreatePanel } from "./BasicProfileCreatePanel";
import { BasicProfileUpdatePanel } from "./BasicProfileUpdatePanel";
import { BasicProfileDeletePanel } from "./BasicProfileDeletePanel";
import { AddressProfileCreatePanel } from "./AddressProfileCreatePanel";
import { AddressProfileUpdatePanel } from "./AddressProfileUpdatePanel";
import { AddressProfileDeletePanel } from "./AddressProfileDeletePanel";
import { ProfileEventCreatePanel } from "./ProfileEventCreatePanel";
import { ProfileEventUpdatePanel } from "./ProfileEventUpdatePanel";
import { ProfileEventDeletePanel } from "./ProfileEventDeletePanel";
import { ProfilePictureDeletePanel } from "./ProfilePictureDeletePanel";

type PictureProfileMode = "read" | "create" | "edit" | "delete";
type OverviewProfileMode =
  | "read"
  | "create-basic"
  | "edit-basic"
  | "create-address"
  | "edit-address";
type EventFormMode = "create" | "edit";
type PictureDraft = {
  file: File;
  previewUrl: string;
};

type FlexibleProfilePicture = ProfilePicture & {
  url?: string | null;
  picture_url?: string | null;
  profile_picture_url?: string | null;
  cloudinary_url?: string | null;
  file_url?: string | null;
  image?: string | null;
};

function formatValue(value: string | number | boolean | null | undefined) {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  if (value === null || value === undefined || value === "") {
    return "Not added yet";
  }

  return String(value);
}

function getPictureUrl(picture: FlexibleProfilePicture | null | undefined) {
  return (
    picture?.secure_url ||
    picture?.image_url ||
    picture?.url ||
    picture?.picture_url ||
    picture?.profile_picture_url ||
    picture?.cloudinary_url ||
    picture?.file_url ||
    picture?.image ||
    ""
  );
}

function getProfilePictureUrl(
  profile: MyProfile | undefined,
  picture: FlexibleProfilePicture | null | undefined,
) {
  return (
    getPictureUrl(picture) ||
    getPictureUrl(profile?.picture) ||
    getPictureUrl(profile?.profile_picture)
  );
}

function isAllowedImage(file: File) {
  return file.type === "image/jpeg" || file.type === "image/png";
}

function getEventId(event: ProfileEvent) {
  return event.event_id ?? event.id ?? "unknown-event";
}

function formatEventSummary(event: ProfileEvent) {
  const name = formatValue(event.event_name);
  const date = formatValue(event.event_date);
  const recurring = event.recurring ? "Recurring" : "One time";

  return `${name} - ${date} - ${recurring}`;
}

type DetailRowProps = {
  label: string;
  value: string | number | boolean | null | undefined;
};

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="profile-detail-row">
      <strong>{label}</strong>
      <span>{formatValue(value)}</span>
    </div>
  );
}

export function MyProfilePanel() {
  const [overviewMode, setOverviewMode] =
    useState<OverviewProfileMode>("read");
  const [pictureMode, setPictureMode] =
    useState<PictureProfileMode>("read");
  const [eventFormMode, setEventFormMode] = useState<EventFormMode | null>(
    null,
  );
  const [isEventDeleteOpen, setIsEventDeleteOpen] = useState(false);
  const [pictureClientError, setPictureClientError] = useState("");
  const [pictureDraft, setPictureDraft] = useState<PictureDraft | null>(null);
  const [isPictureUploadWarningOpen, setIsPictureUploadWarningOpen] =
    useState(false);
  const [isOverviewBasicDeleteOpen, setIsOverviewBasicDeleteOpen] =
    useState(false);
  const [isOverviewAddressDeleteOpen, setIsOverviewAddressDeleteOpen] =
    useState(false);
  const [selectedEvent, setSelectedEvent] = useState<ProfileEvent | null>(null);
  const pictureInputRef = useRef<HTMLInputElement | null>(null);
  const profileQuery = useMyProfile();
  const createPicture = useCreateMyProfilePicture();
  const updatePicture = useUpdateMyProfilePicture();
  const result = profileQuery.data;
  const profile = result?.ok ? result.data : undefined;
  const canUseProfileSnapshot = Boolean(result?.ok);
  const identityProfile = profile?.identity ?? null;
  const profilePictureQuery = useMyProfilePicture(canUseProfileSnapshot);
  const profilePicture = profilePictureQuery.data?.ok
    ? (profilePictureQuery.data.data as FlexibleProfilePicture | null)
    : undefined;
  const basicProfile = profile?.basic ?? profile?.basic_data ?? null;
  const addressProfile = profile?.address ?? null;
  const completeProfilePicture =
    profile?.picture ?? profile?.profile_picture ?? null;
  const profilePictureUrl = getProfilePictureUrl(profile, profilePicture);
  const overviewTitle = basicProfile?.occupation || "Profile overview";
  const overviewBio = basicProfile?.bio || "No bio added yet";
  const hasBasicProfile = canUseProfileSnapshot && Boolean(basicProfile);
  const hasAddressProfile = canUseProfileSnapshot && Boolean(addressProfile);
  const hasProfilePicture =
    canUseProfileSnapshot &&
    Boolean(
      profilePicture?.id ||
        profilePicture?.public_id ||
        completeProfilePicture?.id ||
        completeProfilePicture?.public_id ||
        profilePictureUrl,
    );
  const displayedProfilePictureUrl =
    pictureDraft?.previewUrl || profilePictureUrl;
  const isPictureUploading = createPicture.isPending || updatePicture.isPending;

  useEffect(() => {
    return () => {
      if (pictureDraft?.previewUrl) {
        URL.revokeObjectURL(pictureDraft.previewUrl);
      }
    };
  }, [pictureDraft?.previewUrl]);

  function clearPictureDraft() {
    setPictureDraft(null);
    setPictureClientError("");
    setIsPictureUploadWarningOpen(false);

    if (pictureInputRef.current) {
      pictureInputRef.current.value = "";
    }
  }

  function openPicturePicker(
    nextMode: Extract<PictureProfileMode, "create" | "edit">,
    options: { keepUploadModalOpen?: boolean } = {},
  ) {
    setPictureMode(nextMode);
    setPictureClientError("");
    setIsPictureUploadWarningOpen(Boolean(options.keepUploadModalOpen));

    if (pictureInputRef.current) {
      pictureInputRef.current.value = "";
      pictureInputRef.current.click();
    }
  }

  function handlePictureFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    setPictureClientError("");

    if (!file) {
      if (!pictureDraft) {
        setPictureMode("read");
        setIsPictureUploadWarningOpen(false);
        return;
      }

      setIsPictureUploadWarningOpen(true);
      return;
    }

    if (!isAllowedImage(file)) {
      setPictureClientError("Only JPEG and PNG images are allowed.");
      setIsPictureUploadWarningOpen(Boolean(pictureDraft));
      event.target.value = "";
      return;
    }

    setPictureDraft({
      file,
      previewUrl: URL.createObjectURL(file),
    });
    setPictureMode(hasProfilePicture ? "edit" : "create");
    setIsPictureUploadWarningOpen(true);
  }

  async function uploadPictureDraft() {
    if (!pictureDraft) {
      setPictureClientError("Choose a JPEG or PNG image first.");
      openPicturePicker(hasProfilePicture ? "edit" : "create");
      return;
    }

    const formData = new FormData();
    formData.append("image", pictureDraft.file);

    const result =
      pictureMode === "create"
        ? await createPicture.mutateAsync(formData)
        : await updatePicture.mutateAsync(formData);

    if (result.ok) {
      clearPictureDraft();
      setPictureMode("read");
      void profilePictureQuery.refetch();
      void profileQuery.refetch();
      return;
    }

    setPictureClientError("The server could not save that image.");
  }

  function cancelPictureWorkflow() {
    clearPictureDraft();
    setPictureMode("read");
  }

  function closeEventForm() {
    setEventFormMode(null);
    setSelectedEvent(null);
  }

  function openEventCreateForm() {
    setSelectedEvent(null);
    setIsEventDeleteOpen(false);
    setEventFormMode("create");
  }

  function openEventUpdateForm(event: ProfileEvent) {
    setSelectedEvent(event);
    setIsEventDeleteOpen(false);
    setEventFormMode("edit");
  }

  function openEventDeleteWarning(event: ProfileEvent) {
    setSelectedEvent(event);
    setEventFormMode(null);
    setIsEventDeleteOpen(true);
  }

  function renderPictureUploadConfirmModal() {
    if (!isPictureUploadWarningOpen || !pictureDraft) {
      return null;
    }

    const isCreateMode = pictureMode === "create";

    return (
      <div className="warning-modal-backdrop" role="presentation">
        <section
          aria-labelledby="profile-picture-confirm-title"
          aria-modal="true"
          className="warning-modal profile-picture-confirm-modal"
          role="dialog"
        >
          <div className="warning-modal__copy">
            <h2 id="profile-picture-confirm-title">
              {isCreateMode
                ? "Upload profile picture?"
                : "Replace profile picture?"}
            </h2>
            <p>Preview the selected image before saving it to your profile.</p>
          </div>

          <div className="profile-picture-confirm-preview">
            <img
              alt="Selected profile picture preview"
              className="profile-picture-confirm-image"
              src={pictureDraft.previewUrl}
            />
            <div className="profile-picture-confirm-file">
              <strong>{pictureDraft.file.name}</strong>
              <span>{Math.ceil(pictureDraft.file.size / 1024)} KB</span>
            </div>
          </div>

          {pictureClientError ? (
            <div className="auth-error" role="alert">
              {pictureClientError}
            </div>
          ) : null}

          {createPicture.data && !createPicture.data.ok ? (
            <div className="auth-error" role="alert">
              {createPicture.data.message}
            </div>
          ) : null}

          {updatePicture.data && !updatePicture.data.ok ? (
            <div className="auth-error" role="alert">
              {updatePicture.data.message}
            </div>
          ) : null}

          {createPicture.isError || updatePicture.isError ? (
            <div className="auth-error" role="alert">
              Profile picture upload failed before the server returned a
              response.
            </div>
          ) : null}

          <div className="warning-modal__actions profile-picture-confirm-actions">
            <Button
              disabled={isPictureUploading}
              onClick={() =>
                openPicturePicker(hasProfilePicture ? "edit" : "create", {
                  keepUploadModalOpen: true,
                })
              }
              type="button"
              variant="secondary"
            >
              Choose different picture
            </Button>
            <Button
              disabled={isPictureUploading}
              onClick={cancelPictureWorkflow}
              type="button"
              variant="secondary"
            >
              Cancel
            </Button>
            <Button
              disabled={isPictureUploading}
              onClick={() => void uploadPictureDraft()}
              type="button"
            >
              {isPictureUploading
                ? "Uploading..."
                : isCreateMode
                  ? "Confirm upload"
                  : "Confirm replace"}
            </Button>
          </div>
        </section>
      </div>
    );
  }

  function showOverviewMode(nextMode: OverviewProfileMode) {
    setSelectedEvent(null);
    setOverviewMode(nextMode);
  }

  function renderOverviewEditorPanel() {
    const backToOverview = () => showOverviewMode("read");

    if (overviewMode === "create-basic") {
      return (
        <div className="profile-overview-editor">
          <div className="profile-mode-toolbar">
            <Button onClick={backToOverview} type="button" variant="secondary">
              Back to overview
            </Button>
          </div>
          <BasicProfileCreatePanel
            onCreated={() => {
              showOverviewMode("read");
              void profileQuery.refetch();
            }}
          />
        </div>
      );
    }

    if (overviewMode === "edit-basic") {
      return (
        <div className="profile-overview-editor">
          <div className="profile-mode-toolbar">
            <Button onClick={backToOverview} type="button" variant="secondary">
              Back to overview
            </Button>
          </div>
          <BasicProfileUpdatePanel
            initialBasicProfile={basicProfile}
            onUpdated={() => {
              showOverviewMode("read");
              void profileQuery.refetch();
            }}
          />
        </div>
      );
    }

    if (overviewMode === "create-address") {
      return (
        <div className="profile-overview-editor">
          <div className="profile-mode-toolbar">
            <Button onClick={backToOverview} type="button" variant="secondary">
              Back to overview
            </Button>
          </div>
          <AddressProfileCreatePanel
            onCreated={() => {
              showOverviewMode("read");
              void profileQuery.refetch();
            }}
          />
        </div>
      );
    }

    if (overviewMode === "edit-address") {
      return (
        <div className="profile-overview-editor">
          <div className="profile-mode-toolbar">
            <Button onClick={backToOverview} type="button" variant="secondary">
              Back to overview
            </Button>
          </div>
          <AddressProfileUpdatePanel
            initialAddressProfile={addressProfile}
            onUpdated={() => {
              showOverviewMode("read");
              void profileQuery.refetch();
            }}
          />
        </div>
      );
    }

    return null;
  }

  function renderOverviewPicturePanel() {
    if (pictureMode === "delete" && hasProfilePicture) {
      return (
        <ProfilePictureDeletePanel
          onCancel={() => setPictureMode("read")}
          onDeleted={() => {
            cancelPictureWorkflow();
            void profilePictureQuery.refetch();
            void profileQuery.refetch();
          }}
        />
      );
    }

    return null;
  }

  return (
    <section className="profile-workspace" aria-label="My profile">
      <section className="profile-overview-panel">
            <div className="profile-overview-header">
              <div className="profile-picture-control">
                <div className="profile-overview-avatar" aria-hidden="true">
                  {displayedProfilePictureUrl ? (
                    <img
                      alt=""
                      className="profile-overview-image"
                      src={displayedProfilePictureUrl}
                    />
                  ) : (
                    <span>ME</span>
                  )}
                </div>

                <input
                  accept="image/jpeg,image/png"
                  className="profile-picture-file-input"
                  disabled={isPictureUploading}
                  onChange={handlePictureFileChange}
                  ref={pictureInputRef}
                  type="file"
                />

                <div
                  className="profile-picture-icon-actions"
                  aria-label="Profile picture actions"
                >
                  {canUseProfileSnapshot ? (
                    !hasProfilePicture ? (
                      <button
                        aria-label="Add profile picture"
                        className="profile-picture-icon-button motion-button-switch"
                        onClick={() => openPicturePicker("create")}
                        type="button"
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M12 5V19" />
                          <path d="M5 12H19" />
                        </svg>
                      </button>
                    ) : (
                      <>
                        <button
                          aria-label="Replace profile picture"
                          className="profile-picture-icon-button motion-button-switch"
                          onClick={() => openPicturePicker("edit")}
                          type="button"
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M4 20H8L18.5 9.5A2.8 2.8 0 0 0 14.5 5.5L4 16V20Z" />
                            <path d="M13.5 6.5L17.5 10.5" />
                          </svg>
                        </button>

                        <button
                          aria-label="Delete profile picture"
                          className="profile-picture-icon-button profile-picture-icon-button--danger motion-button-switch"
                          onClick={() => {
                            clearPictureDraft();
                            setPictureMode("delete");
                          }}
                          type="button"
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M4 7H20" />
                            <path d="M10 11V17" />
                            <path d="M14 11V17" />
                            <path d="M6 7L7 20H17L18 7" />
                            <path d="M9 7V4H15V7" />
                          </svg>
                        </button>
                      </>
                    )
                  ) : null}
                </div>
              </div>

              <div className="profile-overview-copy">
                <span className="section-kicker">Overview</span>
                <h3>{overviewTitle}</h3>
                <p>{overviewBio}</p>
                {identityProfile ? (
                  <dl className="profile-identity-list">
                    <div>
                      <dt>Full name</dt>
                      <dd>{formatValue(identityProfile.full_name)}</dd>
                    </div>
                    <div>
                      <dt>Username</dt>
                      <dd>{formatValue(identityProfile.username)}</dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{formatValue(identityProfile.email)}</dd>
                    </div>
                    <div>
                      <dt>Contact</dt>
                      <dd>{formatValue(identityProfile.contact_number)}</dd>
                    </div>
                  </dl>
                ) : null}
              </div>

              <Button
                disabled={profileQuery.isFetching}
                onClick={() => void profileQuery.refetch()}
                type="button"
                variant="secondary"
              >
                {profileQuery.isFetching ? "Refreshing..." : "Refresh"}
              </Button>
            </div>

            {profileQuery.isPending ? (
              <div className="auth-success" role="status">
                <strong>Loading profile...</strong>
                <p>Fetching your latest profile details.</p>
              </div>
            ) : null}

            {!profileQuery.isPending && result && !result.ok ? (
              <div className="auth-error" role="alert">
                {result.message}
              </div>
            ) : null}

            {!profileQuery.isPending && profileQuery.isError ? (
              <div className="auth-error" role="alert">
                Profile request failed before the server returned a response.
              </div>
            ) : null}

            {overviewMode !== "read" ? (
              renderOverviewEditorPanel()
            ) : profile ? (
              <div className="profile-overview-grid">
                <section className="profile-detail-group">
                  <div className="profile-detail-group-header">
                    <h3>Basic</h3>
                    <div className="profile-detail-group-actions">
                      <Button
                        onClick={() =>
                          showOverviewMode(
                            hasBasicProfile ? "edit-basic" : "create-basic",
                          )
                        }
                        type="button"
                        variant="secondary"
                      >
                        {hasBasicProfile
                          ? "Update basic profile"
                          : "Create basic profile"}
                      </Button>

                      {hasBasicProfile ? (
                        <Button
                          onClick={() => setIsOverviewBasicDeleteOpen(true)}
                          type="button"
                          variant="danger"
                        >
                          Delete basic profile
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <DetailRow label="Bio" value={basicProfile?.bio} />
                  <DetailRow
                    label="Date of birth"
                    value={basicProfile?.date_of_birth}
                  />
                  <DetailRow label="Gender" value={basicProfile?.gender} />
                  <DetailRow
                    label="Occupation"
                    value={basicProfile?.occupation}
                  />
                  <DetailRow label="Website" value={basicProfile?.website} />
                </section>

                <section className="profile-detail-group">
                  <div className="profile-detail-group-header">
                    <h3>Address</h3>
                    <div className="profile-detail-group-actions">
                      <Button
                        onClick={() =>
                          showOverviewMode(
                            hasAddressProfile
                              ? "edit-address"
                              : "create-address",
                          )
                        }
                        type="button"
                        variant="secondary"
                      >
                        {hasAddressProfile
                          ? "Update address"
                          : "Create address"}
                      </Button>

                      {hasAddressProfile ? (
                        <Button
                          onClick={() => setIsOverviewAddressDeleteOpen(true)}
                          type="button"
                          variant="danger"
                        >
                          Delete address
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <DetailRow
                    label="Address line 1"
                    value={addressProfile?.address_line_1}
                  />
                  <DetailRow
                    label="Address line 2"
                    value={addressProfile?.address_line_2}
                  />
                  <DetailRow label="City" value={addressProfile?.city} />
                  <DetailRow label="State" value={addressProfile?.state} />
                  <DetailRow
                    label="Postal code"
                    value={addressProfile?.postal_code}
                  />
                  <DetailRow label="Country" value={addressProfile?.country} />
                </section>

                <section className="profile-detail-group profile-detail-group--wide">
                  <div className="profile-detail-group-header">
                    <h3>Events</h3>
                    <Button
                      onClick={openEventCreateForm}
                      type="button"
                      variant="secondary"
                    >
                      Add event
                    </Button>
                  </div>
                  {profile.events && profile.events.length > 0 ? (
                    <div className="profile-record-list">
                      {profile.events.map((event, index) => {
                        const eventId = getEventId(event);

                        return (
                          <article
                            className="profile-record-item"
                            key={`${String(eventId)}-${index}`}
                          >
                            <div className="profile-record-header">
                              <div>
                                <h3>
                                  {event.event_name || `Event ${index + 1}`}
                                </h3>
                                <span>{formatEventSummary(event)}</span>
                              </div>

                              <div className="profile-record-actions">
                                <Button
                                  onClick={() => openEventUpdateForm(event)}
                                  type="button"
                                  variant="secondary"
                                >
                                  Edit
                                </Button>
                                <Button
                                  onClick={() => openEventDeleteWarning(event)}
                                  type="button"
                                  variant="danger"
                                >
                                  Delete
                                </Button>
                              </div>
                            </div>

                            <div className="profile-record-grid">
                              <DetailRow label="Event ID" value={eventId} />
                              <DetailRow
                                label="Event name"
                                value={event.event_name}
                              />
                              <DetailRow
                                label="Event date"
                                value={event.event_date}
                              />
                              <DetailRow
                                label="Description"
                                value={event.description}
                              />
                              <DetailRow
                                label="Recurring"
                                value={event.recurring}
                              />
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <p>No events added yet</p>
                  )}
                </section>
              </div>
            ) : null}

            {renderPictureUploadConfirmModal()}
            {renderOverviewPicturePanel()}
            {isOverviewBasicDeleteOpen ? (
              <BasicProfileDeletePanel
                onCancel={() => setIsOverviewBasicDeleteOpen(false)}
                onDeleted={() => {
                  setIsOverviewBasicDeleteOpen(false);
                  setOverviewMode("read");
                  void profileQuery.refetch();
                }}
              />
            ) : null}
            {isOverviewAddressDeleteOpen ? (
              <AddressProfileDeletePanel
                onCancel={() => setIsOverviewAddressDeleteOpen(false)}
                onDeleted={() => {
                  setIsOverviewAddressDeleteOpen(false);
                  setOverviewMode("read");
                  void profileQuery.refetch();
                }}
              />
            ) : null}
            <FormModal
              description="Add a date-based profile event."
              isOpen={eventFormMode === "create"}
              onClose={closeEventForm}
              title="Add event"
            >
              <ProfileEventCreatePanel
                onCreated={() => {
                  closeEventForm();
                  void profileQuery.refetch();
                }}
                pendingLabel="Adding..."
                showHeading={false}
                submitLabel="Add event"
              />
            </FormModal>
            <FormModal
              description="Update the selected profile event."
              isOpen={eventFormMode === "edit" && Boolean(selectedEvent)}
              onClose={closeEventForm}
              title="Update event"
            >
              <ProfileEventUpdatePanel
                clearLabel="Clear form"
                event={selectedEvent}
                onUpdated={() => {
                  closeEventForm();
                  void profileQuery.refetch();
                }}
                showHeading={false}
                submitLabel="Update event"
              />
            </FormModal>
            {isEventDeleteOpen && selectedEvent ? (
              <ProfileEventDeletePanel
                event={selectedEvent}
                onCancel={() => {
                  setIsEventDeleteOpen(false);
                  setSelectedEvent(null);
                }}
                onDeleted={() => {
                  setIsEventDeleteOpen(false);
                  setSelectedEvent(null);
                  void profileQuery.refetch();
                }}
              />
            ) : null}
          </section>
    </section>
  );
}
