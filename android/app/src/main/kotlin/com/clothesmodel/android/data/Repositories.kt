package com.clothesmodel.android.data

import com.clothesmodel.contract.model.AddOutfitLayerRequest
import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.CreateOutfitBranchRequest
import com.clothesmodel.contract.model.CreateOutfitSessionRequest
import com.clothesmodel.contract.model.FinishFailedRequest
import com.clothesmodel.contract.model.LayerRole
import com.clothesmodel.contract.model.OutfitLayerResult
import com.clothesmodel.contract.model.OutfitRoute
import com.clothesmodel.contract.model.OutfitSession
import com.clothesmodel.contract.model.ReapplyOutfitLayerRequest
import com.clothesmodel.contract.model.RemoveOutfitLayerRequest
import com.clothesmodel.contract.model.RetryJobItemRequest
import com.clothesmodel.contract.model.SelectOutfitRevisionRequest
import com.clothesmodel.contract.model.SwitchOutfitRouteRequest
import com.clothesmodel.contract.model.UpdateOutfitBranchRequest
import com.clothesmodel.contract.model.UpdateOutfitSessionRequest
import java.io.IOException
import java.util.UUID
import retrofit2.Response

private suspend fun <T> networkSafe(block: suspend () -> Outcome<T>): Outcome<T> = try {
    block()
} catch (error: IOException) {
    Outcome.Problem(networkProblem())
}

internal suspend fun <T, R> Response<T>.toOutcome(
    events: AuthenticationEvents,
    transform: (T) -> R,
): Outcome<R> = when {
    isSuccessful -> {
        val body = body()
        if (body == null) {
            Outcome.Problem(
                ProblemModel("empty_response", "服务器返回了空结果。", code(), true),
            )
        } else {
            Outcome.Success(transform(body))
        }
    }

    code() == 401 -> {
        events.onAuthenticationExpired()
        Outcome.AuthenticationExpired
    }

    else -> Outcome.Problem(ProblemParser.from(errorBody()))
}

class AssetRepository(
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) {
    suspend fun list(
        kind: AssetKindFilter = AssetKindFilter.ALL,
        cursor: String? = null,
        limit: Int = 50,
    ): Outcome<Page<AssetModel>> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.assets.listAssets(
            cursor = cursor,
            limit = limit,
            kind = kind.wire?.let(::wireKind),
        ).toOutcome(events) { it.toPage() }
    }

    suspend fun get(assetId: UUID): Outcome<AssetModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.assets.getAsset(assetId).toOutcome(events) { it.toModel() }
    }

    suspend fun setFavorite(assetId: UUID, favorite: Boolean): Outcome<AssetModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.assets.updateAsset(assetId, AssetUpdateRequestFactory.create(favorite))
            .toOutcome(events) { it.toModel() }
    }

    suspend fun references(assetId: UUID): Outcome<Page<AssetReferenceModel>> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.assets.listAssetReferences(assetId).toOutcome(events) { it.toPage() }
    }

    suspend fun deleteContent(assetId: UUID): Outcome<AssetModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.assets.deleteAssetContent(assetId).toOutcome(events) { it.asset.toModel() }
    }
}

class JobRepository(
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) {
    suspend fun list(
        state: JobStateDomain? = null,
        cursor: String? = null,
        limit: Int = 50,
    ): Outcome<Page<JobModel>> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.listJobs(cursor = cursor, limit = limit, state = state?.toWire())
            .toOutcome(events) { it.toPage() }
    }

    suspend fun get(jobId: UUID): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.getJob(jobId).toOutcome(events) { it.toModel() }
    }

    suspend fun create(request: CreateJobRequest, idempotencyKey: String): Outcome<JobModel> =
        networkSafe {
            val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
            services.jobs.createJob(idempotencyKey, request).toOutcome(events) { it.toModel() }
        }

    suspend fun cancelJob(jobId: UUID, idempotencyKey: String): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.cancelJob(jobId, idempotencyKey).toOutcome(events) { it.job.toModel() }
    }

    suspend fun cancelItem(itemId: UUID, idempotencyKey: String): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.cancelJobItem(itemId, idempotencyKey).toOutcome(events) { it.job.toModel() }
    }

    suspend fun retryItem(
        itemId: UUID,
        idempotencyKey: String,
        providerId: UUID? = null,
        reason: String? = null,
    ): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        val body = if (providerId == null && reason == null) {
            null
        } else {
            RetryJobItemRequest(providerId = providerId, reason = reason)
        }
        services.jobs.retryJobItem(itemId, idempotencyKey, body).toOutcome(events) {
            it.job.toModel()
        }
    }

    suspend fun requeryItem(itemId: UUID, idempotencyKey: String): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.requeryJobItem(itemId, idempotencyKey).toOutcome(events) { it.job.toModel() }
    }

    suspend fun finishFailed(
        itemId: UUID,
        idempotencyKey: String,
        reason: String,
    ): Outcome<JobModel> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.jobs.finishJobItemAsFailed(itemId, idempotencyKey, FinishFailedRequest(reason))
            .toOutcome(events) { it.job.toModel() }
    }
}

class ProviderRepository(
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) {
    suspend fun available(cursor: String? = null, limit: Int = 50): Outcome<Page<ProviderModel>> =
        networkSafe {
            val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
            services.providers.listAvailableProviders(cursor = cursor, limit = limit)
                .toOutcome(events) { it.toPage() }
        }
}

class ContentRepository(
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) : ContentFetcher {
    override suspend fun fetch(assetId: UUID): Outcome<ByteArray> = download(assetId)

    suspend fun download(assetId: UUID): Outcome<ByteArray> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        val response = services.assets.downloadAssetContent(assetId)
        when {
            response.isSuccessful -> {
                val bytes = response.body()?.bytes() ?: ByteArray(0)
                Outcome.Success(bytes)
            }

            response.code() == 401 -> {
                events.onAuthenticationExpired()
                Outcome.AuthenticationExpired
            }

            else -> Outcome.Problem(ProblemParser.from(response.errorBody()))
        }
    }
}

private fun JobStateDomain.toWire(): com.clothesmodel.contract.model.JobState =
    when (this) {
        JobStateDomain.QUEUED -> com.clothesmodel.contract.model.JobState.queued
        JobStateDomain.WAITING_PROVIDER -> com.clothesmodel.contract.model.JobState.waiting_provider
        JobStateDomain.PREPARING -> com.clothesmodel.contract.model.JobState.preparing
        JobStateDomain.RUNNING -> com.clothesmodel.contract.model.JobState.running
        JobStateDomain.NEEDS_ATTENTION -> com.clothesmodel.contract.model.JobState.needs_attention
        JobStateDomain.SUCCEEDED -> com.clothesmodel.contract.model.JobState.succeeded
        JobStateDomain.PARTIALLY_SUCCEEDED ->
            com.clothesmodel.contract.model.JobState.partially_succeeded

        JobStateDomain.FAILED -> com.clothesmodel.contract.model.JobState.failed
        JobStateDomain.CANCELLED -> com.clothesmodel.contract.model.JobState.cancelled
        JobStateDomain.UNKNOWN -> com.clothesmodel.contract.model.JobState.unknown
    }

private object AssetUpdateRequestFactory {
    fun create(favorite: Boolean): com.clothesmodel.contract.model.AssetUpdateRequest =
        com.clothesmodel.contract.model.AssetUpdateRequest(favorite = favorite)
}

interface OutfitRepository {
    suspend fun list(limit: Int = 50): Outcome<List<OutfitSession>>
    suspend fun create(
        personAssetId: UUID,
        name: String?,
        idempotencyKey: String,
    ): Outcome<OutfitSession>

    suspend fun setFavorite(sessionId: UUID, favorite: Boolean): Outcome<OutfitSession>

    suspend fun get(sessionId: UUID): Outcome<OutfitSession>

    suspend fun addLayer(
        sessionId: UUID,
        branchId: UUID,
        role: LayerRole,
        garmentAssetId: UUID,
        providerId: UUID?,
        candidateCount: Int,
        idempotencyKey: String,
    ): Outcome<OutfitLayerResult>

    suspend fun selectRevision(
        sessionId: UUID,
        branchId: UUID,
        revisionId: UUID,
        jobItemId: UUID,
        outputId: UUID,
        idempotencyKey: String,
    ): Outcome<OutfitSession>

    suspend fun removeLayer(
        sessionId: UUID,
        branchId: UUID,
        layerId: UUID,
        mode: RemoveOutfitLayerRequest.Mode?,
    ): Outcome<OutfitSession>

    suspend fun switchRoute(
        sessionId: UUID,
        route: OutfitRoute,
        idempotencyKey: String,
    ): Outcome<OutfitSession>

    suspend fun createBranch(
        sessionId: UUID,
        name: String?,
        idempotencyKey: String,
    ): Outcome<OutfitSession>

    suspend fun setMainline(sessionId: UUID, branchId: UUID): Outcome<OutfitSession>

    suspend fun deleteBranch(sessionId: UUID, branchId: UUID): Outcome<OutfitSession>

    suspend fun reapplyLayer(
        sessionId: UUID,
        branchId: UUID,
        layerId: UUID,
        providerId: UUID?,
        candidateCount: Int,
        idempotencyKey: String,
    ): Outcome<OutfitLayerResult>
}

class NetworkOutfitRepository(
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) : OutfitRepository {
    override suspend fun list(limit: Int): Outcome<List<OutfitSession>> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.listOutfitSessions(limit = limit).toOutcome(events) { it.items }
    }

    override suspend fun create(
        personAssetId: UUID,
        name: String?,
        idempotencyKey: String,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.createOutfitSession(
            idempotencyKey,
            CreateOutfitSessionRequest(personAssetId = personAssetId, name = name),
        ).toOutcome(events) { it }
    }

    override suspend fun setFavorite(
        sessionId: UUID,
        favorite: Boolean,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.updateOutfitSession(
            sessionId,
            UpdateOutfitSessionRequest(favorite = favorite),
        ).toOutcome(events) { it }
    }

    override suspend fun get(sessionId: UUID): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.getOutfitSession(sessionId).toOutcome(events) { it }
    }

    override suspend fun addLayer(
        sessionId: UUID,
        branchId: UUID,
        role: LayerRole,
        garmentAssetId: UUID,
        providerId: UUID?,
        candidateCount: Int,
        idempotencyKey: String,
    ): Outcome<OutfitLayerResult> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.addOutfitLayer(
            sessionId,
            branchId,
            idempotencyKey,
            AddOutfitLayerRequest(
                role = role,
                garmentAssetId = garmentAssetId,
                providerId = providerId,
                candidateCount = candidateCount,
            ),
        ).toOutcome(events) { it }
    }

    override suspend fun selectRevision(
        sessionId: UUID,
        branchId: UUID,
        revisionId: UUID,
        jobItemId: UUID,
        outputId: UUID,
        idempotencyKey: String,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.selectOutfitRevision(
            sessionId,
            branchId,
            revisionId,
            idempotencyKey,
            SelectOutfitRevisionRequest(jobItemId = jobItemId, outputId = outputId),
        ).toOutcome(events) { it }
    }

    override suspend fun removeLayer(
        sessionId: UUID,
        branchId: UUID,
        layerId: UUID,
        mode: RemoveOutfitLayerRequest.Mode?,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.removeOutfitLayer(
            sessionId,
            branchId,
            layerId,
            mode?.let { RemoveOutfitLayerRequest(mode = it) },
        ).toOutcome(events) { it }
    }

    override suspend fun switchRoute(
        sessionId: UUID,
        route: OutfitRoute,
        idempotencyKey: String,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.switchOutfitRoute(
            sessionId,
            idempotencyKey,
            SwitchOutfitRouteRequest(route = route),
        ).toOutcome(events) { it }
    }

    override suspend fun createBranch(
        sessionId: UUID,
        name: String?,
        idempotencyKey: String,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.createOutfitBranch(
            sessionId,
            idempotencyKey,
            CreateOutfitBranchRequest(name = name),
        ).toOutcome(events) { it }
    }

    override suspend fun setMainline(sessionId: UUID, branchId: UUID): Outcome<OutfitSession> =
        networkSafe {
            val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
            services.outfits.updateOutfitBranch(
                sessionId,
                branchId,
                UpdateOutfitBranchRequest(mainline = true),
            ).toOutcome(events) { it }
        }

    override suspend fun deleteBranch(
        sessionId: UUID,
        branchId: UUID,
    ): Outcome<OutfitSession> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.deleteOutfitBranch(sessionId, branchId).toOutcome(events) { it }
    }

    override suspend fun reapplyLayer(
        sessionId: UUID,
        branchId: UUID,
        layerId: UUID,
        providerId: UUID?,
        candidateCount: Int,
        idempotencyKey: String,
    ): Outcome<OutfitLayerResult> = networkSafe {
        val services = factory.services() ?: return@networkSafe Outcome.AuthenticationExpired
        services.outfits.reapplyOutfitLayer(
            sessionId,
            branchId,
            layerId,
            idempotencyKey,
            ReapplyOutfitLayerRequest(
                providerId = providerId,
                candidateCount = candidateCount,
            ),
        ).toOutcome(events) { it }
    }
}
