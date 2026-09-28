package com.clothesmodel.android.data

import com.clothesmodel.contract.model.Asset
import com.clothesmodel.contract.model.AssetKind as WireAssetKind
import com.clothesmodel.contract.model.AssetPage
import com.clothesmodel.contract.model.AssetReference
import com.clothesmodel.contract.model.AssetReferencePage
import com.clothesmodel.contract.model.GeneratedOutput
import com.clothesmodel.contract.model.JobItem
import com.clothesmodel.contract.model.JobPage
import com.clothesmodel.contract.model.ProviderPage
import com.clothesmodel.contract.model.ProviderSummary
import com.clothesmodel.contract.model.TryOnJob

fun Asset.toModel(): AssetModel = AssetModel(
    id = id,
    kind = kind.value,
    favorite = favorite,
    lifecycle = when (lifecycle.value) {
        "active" -> AssetLifecycle.ACTIVE
        "deleted_content" -> AssetLifecycle.DELETED_CONTENT
        "expired" -> AssetLifecycle.EXPIRED
        else -> AssetLifecycle.UNKNOWN
    },
    contentAvailable = contentAvailable,
    width = width,
    height = height,
    createdAt = createdAt,
    garmentCategory = garmentCategory?.let { GarmentCategory.fromWire(it.value) },
    garmentSource = garmentSource?.let { GarmentSource.fromWire(it.value) },
    qualityWarnings = qualityWarnings.orEmpty(),
)

fun AssetReference.toModel(): AssetReferenceModel = AssetReferenceModel(
    id = id,
    assetId = assetId,
    sourceKind = sourceKind.value,
    sourceId = sourceId,
    label = label,
    active = active,
    createdAt = createdAt,
)

fun ProviderSummary.toModel(): ProviderModel = ProviderModel(
    id = id,
    displayName = displayName,
    availability = ProviderAvailabilityDomain.fromWire(availability.value),
    isDefault = isDefault == true,
    maxCandidates = capabilities.outputConstraints.maxCandidates,
    supportsManualMask = capabilities.manualMask.supported,
    supportsRegionMask = capabilities.regionMask.supported,
    garmentCategories = capabilities.garmentCategories.propertyValues,
    unavailableReason = unavailableReason,
)

fun GeneratedOutput.toModel(): JobOutputModel = JobOutputModel(
    id = id,
    jobItemId = jobItemId,
    assetId = assetId,
    favorite = favorite,
    contentAvailable = contentAvailable,
    seed = seed,
    createdAt = createdAt,
)

fun JobItem.toModel(): CandidateModel = CandidateModel(
    id = id,
    jobId = jobId,
    candidateIndex = candidateIndex,
    state = CandidateStateDomain.fromWire(state.value),
    attempt = attempt,
    blockReason = BlockReasonDomain.fromWire(blockReason?.value),
    retryOfJobItemId = retryOfJobItemId,
    supersededByJobItemId = supersededByJobItemId,
    externalExecutionId = externalExecutionId,
    nextAttemptAt = nextAttemptAt,
    outputs = outputs.map { it.toModel() },
    errorCode = error?.code,
    errorDetail = error?.detail,
    createdAt = createdAt,
    updatedAt = updatedAt,
)

fun TryOnJob.toModel(): JobModel = JobModel(
    id = id,
    state = JobStateDomain.fromWire(state.value),
    candidateCount = generationOptions.candidateCount,
    blockReason = BlockReasonDomain.fromWire(blockReason?.value),
    blockedDetail = blockedDetail,
    nextAttemptAt = nextAttemptAt,
    providerLabel = providerSnapshot.label,
    lockedProviderId = providerConfigRef.providerId,
    garmentAssetId = garmentAssetId,
    maskAssetId = maskAssetId,
    relatedJobId = relatedJobId,
    workflowLabel = workflowSnapshot?.label,
    candidates = items.map { it.toModel() },
    createdAt = createdAt,
    updatedAt = updatedAt,
)

fun AssetPage.toPage(): Page<AssetModel> = Page(
    items = items.orEmpty().map { it.toModel() },
    nextCursor = nextCursor,
    hasMore = hasMore,
)

fun AssetReferencePage.toPage(): Page<AssetReferenceModel> = Page(
    items = items.orEmpty().map { it.toModel() },
    nextCursor = nextCursor,
    hasMore = hasMore,
)

fun ProviderPage.toPage(): Page<ProviderModel> = Page(
    items = items.orEmpty().map { it.toModel() },
    nextCursor = nextCursor,
    hasMore = hasMore,
)

fun JobPage.toPage(): Page<JobModel> = Page(
    items = items.orEmpty().map { it.toModel() },
    nextCursor = nextCursor,
    hasMore = hasMore,
)

fun wireKind(wire: String): WireAssetKind =
    WireAssetKind.entries.firstOrNull { it.value == wire } ?: WireAssetKind.unknown_default_open_api
