package com.clothesmodel.android.data

import java.time.OffsetDateTime
import java.util.UUID

enum class AssetKindFilter(val wire: String?) {
    ALL(null),
    PERSON("person"),
    GARMENT("garment"),
    GENERATED_OUTPUT("generated_output"),
    MASK("mask"),
}

enum class AssetLifecycle {
    ACTIVE,
    DELETED_CONTENT,
    EXPIRED,
    UNKNOWN,
}

enum class GarmentCategory(val wire: String) {
    UPPER_BODY("upper_body"),
    LOWER_BODY("lower_body"),
    DRESS("dress"),
    UNKNOWN("unknown"),
    ;

    companion object {
        fun fromWire(value: String?): GarmentCategory = when (value) {
            "upper_body" -> UPPER_BODY
            "lower_body" -> LOWER_BODY
            "dress" -> DRESS
            else -> UNKNOWN
        }
    }
}

enum class GarmentSource(val wire: String) {
    PHOTO("photo"),
    SCREENSHOT("screenshot"),
    PRODUCT_IMAGE("product_image"),
    EXPERIMENTAL("experimental"),
    UNKNOWN("unknown"),
    ;

    companion object {
        fun fromWire(value: String?): GarmentSource = when (value) {
            "photo" -> PHOTO
            "screenshot" -> SCREENSHOT
            "product_image" -> PRODUCT_IMAGE
            "experimental" -> EXPERIMENTAL
            else -> UNKNOWN
        }
    }
}

data class AssetModel(
    val id: UUID,
    val kind: String,
    val favorite: Boolean,
    val lifecycle: AssetLifecycle,
    val contentAvailable: Boolean,
    val width: Int,
    val height: Int,
    val createdAt: OffsetDateTime,
    val garmentCategory: GarmentCategory?,
    val garmentSource: GarmentSource?,
    val qualityWarnings: List<String>,
) {
    val isDeletedContent: Boolean
        get() = lifecycle == AssetLifecycle.DELETED_CONTENT || !contentAvailable
}

data class AssetReferenceModel(
    val id: UUID,
    val assetId: UUID,
    val sourceKind: String,
    val sourceId: UUID,
    val label: String?,
    val active: Boolean,
    val createdAt: OffsetDateTime,
)

enum class ProviderAvailabilityDomain {
    AVAILABLE,
    TEMPORARILY_OFFLINE,
    UNAVAILABLE_CONFIGURATION,
    DISABLED,
    UNKNOWN,
    ;

    companion object {
        fun fromWire(value: String?): ProviderAvailabilityDomain = when (value) {
            "available" -> AVAILABLE
            "temporarily_offline" -> TEMPORARILY_OFFLINE
            "unavailable_configuration" -> UNAVAILABLE_CONFIGURATION
            "disabled" -> DISABLED
            else -> UNKNOWN
        }
    }
}

data class ProviderModel(
    val id: UUID,
    val displayName: String,
    val availability: ProviderAvailabilityDomain,
    val isDefault: Boolean,
    val maxCandidates: Int,
    val supportsManualMask: Boolean,
    val supportsRegionMask: Boolean,
    val garmentCategories: List<String>,
    val unavailableReason: String?,
) {
    val selectable: Boolean
        get() = availability == ProviderAvailabilityDomain.AVAILABLE
}

enum class JobStateDomain {
    QUEUED,
    WAITING_PROVIDER,
    PREPARING,
    RUNNING,
    NEEDS_ATTENTION,
    SUCCEEDED,
    PARTIALLY_SUCCEEDED,
    FAILED,
    CANCELLED,
    UNKNOWN,
    ;

    val isTerminal: Boolean
        get() = this in setOf(SUCCEEDED, PARTIALLY_SUCCEEDED, FAILED, CANCELLED)

    companion object {
        fun fromWire(value: String?): JobStateDomain = when (value) {
            "queued" -> QUEUED
            "waiting_provider" -> WAITING_PROVIDER
            "preparing" -> PREPARING
            "running" -> RUNNING
            "needs_attention" -> NEEDS_ATTENTION
            "succeeded" -> SUCCEEDED
            "partially_succeeded" -> PARTIALLY_SUCCEEDED
            "failed" -> FAILED
            "cancelled" -> CANCELLED
            else -> UNKNOWN
        }
    }
}

enum class CandidateStateDomain {
    QUEUED,
    WAITING_PROVIDER,
    PREPARING,
    RUNNING,
    NEEDS_ATTENTION,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    UNKNOWN,
    ;

    val isTerminal: Boolean
        get() = this in setOf(SUCCEEDED, FAILED, CANCELLED)

    companion object {
        fun fromWire(value: String?): CandidateStateDomain = when (value) {
            "queued" -> QUEUED
            "waiting_provider" -> WAITING_PROVIDER
            "preparing" -> PREPARING
            "running" -> RUNNING
            "needs_attention" -> NEEDS_ATTENTION
            "succeeded" -> SUCCEEDED
            "failed" -> FAILED
            "cancelled" -> CANCELLED
            else -> UNKNOWN
        }
    }
}

enum class BlockReasonDomain {
    PROVIDER_OFFLINE,
    STORAGE_CAPACITY,
    RETRY_BACKOFF,
    LOCKED_CONFIGURATION_UNAVAILABLE,
    EXTERNAL_STATE_UNKNOWN,
    CONFIGURATION_INVALID,
    UNKNOWN,
    ;

    companion object {
        fun fromWire(value: String?): BlockReasonDomain? = when (value) {
            null -> null
            "provider_offline" -> PROVIDER_OFFLINE
            "storage_capacity" -> STORAGE_CAPACITY
            "retry_backoff" -> RETRY_BACKOFF
            "locked_configuration_unavailable" -> LOCKED_CONFIGURATION_UNAVAILABLE
            "external_state_unknown" -> EXTERNAL_STATE_UNKNOWN
            "configuration_invalid" -> CONFIGURATION_INVALID
            else -> UNKNOWN
        }
    }
}

data class JobOutputModel(
    val id: UUID,
    val jobItemId: UUID,
    val assetId: UUID,
    val favorite: Boolean,
    val contentAvailable: Boolean,
    val seed: Long?,
    val createdAt: OffsetDateTime,
)

data class CandidateModel(
    val id: UUID,
    val jobId: UUID,
    val candidateIndex: Int,
    val state: CandidateStateDomain,
    val attempt: Int,
    val blockReason: BlockReasonDomain?,
    val retryOfJobItemId: UUID?,
    val supersededByJobItemId: UUID?,
    val externalExecutionId: String?,
    val nextAttemptAt: OffsetDateTime?,
    val outputs: List<JobOutputModel>,
    val errorCode: String?,
    val errorDetail: String?,
    val createdAt: OffsetDateTime,
    val updatedAt: OffsetDateTime,
)

data class JobModel(
    val id: UUID,
    val state: JobStateDomain,
    val candidateCount: Int,
    val blockReason: BlockReasonDomain?,
    val blockedDetail: String?,
    val nextAttemptAt: OffsetDateTime?,
    val providerLabel: String,
    val maskAssetId: UUID?,
    val relatedJobId: UUID?,
    val workflowLabel: String?,
    val candidates: List<CandidateModel>,
    val createdAt: OffsetDateTime,
    val updatedAt: OffsetDateTime,
)

data class ProblemModel(
    val code: String,
    val detail: String,
    val status: Int,
    val retryable: Boolean,
    val referenceCount: Int? = null,
)

data class Page<T>(
    val items: List<T>,
    val nextCursor: String?,
    val hasMore: Boolean,
)
