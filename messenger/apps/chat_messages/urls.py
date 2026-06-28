from django.urls import path
from .recovery_views import (
    RecoveryHistoryView,
    RecoveryRewrapView,
)
from .views import (
    EncryptedMessageHistoryView,
    RoomListView,
    SendDirectMessageView,
)
from .recovery_backfill_views import (
    RecoveryBackfillCandidateView,
    RecoveryBackfillView,
)
from .attachment_views import (
    EncryptedAttachmentCompleteView,
    EncryptedAttachmentDeleteView,
    EncryptedAttachmentDownloadView,
    EncryptedAttachmentInitiateView,
)
from .receipt_views import (
    DeliveredReceiptView,
    MessageReceiptSummaryView,
    ReadReceiptView,
)
from .group_history_views import GroupHistoryView
from .group_views import GroupMessageSendView
from .recovery_coverage_views import RecoveryCoverageView
app_name = "chat_messages"


urlpatterns = [
    path(
        "direct/",
        SendDirectMessageView.as_view(),
        name="send-direct-message",
    ),
    path(
        "rooms/",
        RoomListView.as_view(),
        name="room-list",
    ),
    path(
        "rooms/<uuid:room_id>/history/",
        EncryptedMessageHistoryView.as_view(),
        name="encrypted-message-history",
    ),
        
    path(
        "recovery-history/",
        RecoveryHistoryView.as_view(),
        name="recovery-history",
    ),
    path(
        "recovery/rewrap/",
        RecoveryRewrapView.as_view(),
        name="recovery-rewrap",
    ),
    path(
        "recovery/backfill/candidates/",
        RecoveryBackfillCandidateView.as_view(),
        name="recovery-backfill-candidates",
    ),
    path(
        "recovery/backfill/",
        RecoveryBackfillView.as_view(),
        name="recovery-backfill",
    ),
    path(
        "recovery/coverage/",
        RecoveryCoverageView.as_view(),
        name="recovery-coverage",
    ),
    path(
        "group/",
        GroupMessageSendView.as_view(),
        name="group-message-send",
    ),
    path(
        "groups/<uuid:group_id>/history/",
        GroupHistoryView.as_view(),
        name="group-history",
    ),
    path(
        "receipts/delivered/",
        DeliveredReceiptView.as_view(),
        name="message-receipts-delivered",
    ),
    path(
        "receipts/read/",
        ReadReceiptView.as_view(),
        name="message-receipts-read",
    ),
    path(
        "<uuid:message_id>/receipts/",
        MessageReceiptSummaryView.as_view(),
        name="message-receipts-summary",
    ),
    path(
        "attachments/initiate/",
        EncryptedAttachmentInitiateView.as_view(),
        name="encrypted-attachment-initiate",
    ),
    path(
        "attachments/<uuid:attachment_id>/complete/",
        EncryptedAttachmentCompleteView.as_view(),
        name="encrypted-attachment-complete",
    ),
    path(
        "attachments/<uuid:attachment_id>/download/",
        EncryptedAttachmentDownloadView.as_view(),
        name="encrypted-attachment-download",
    ),
    path(
        "attachments/<uuid:attachment_id>/",
        EncryptedAttachmentDeleteView.as_view(),
        name="encrypted-attachment-delete",
    ),
    
]
