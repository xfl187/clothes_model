package com.clothesmodel.android.results

import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.CandidateStateDomain
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobOutputModel
import com.clothesmodel.android.data.JobStateDomain
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun output(available: Boolean) = JobOutputModel(
    id = UUID.randomUUID(),
    jobItemId = UUID.randomUUID(),
    assetId = UUID.randomUUID(),
    favorite = false,
    contentAvailable = available,
    seed = null,
    createdAt = OffsetDateTime.now(),
)

private fun candidate(
    index: Int,
    state: CandidateStateDomain,
    attempt: Int = 1,
    outputs: List<JobOutputModel> = emptyList(),
) = CandidateModel(
    id = UUID.randomUUID(),
    jobId = UUID.randomUUID(),
    candidateIndex = index,
    state = state,
    attempt = attempt,
    blockReason = null,
    retryOfJobItemId = null,
    supersededByJobItemId = null,
    externalExecutionId = null,
    nextAttemptAt = null,
    outputs = outputs,
    errorCode = null,
    errorDetail = null,
    createdAt = OffsetDateTime.now(),
    updatedAt = OffsetDateTime.now(),
)

private fun job(candidates: List<CandidateModel>) = JobModel(
    id = UUID.randomUUID(),
    state = JobStateDomain.PARTIALLY_SUCCEEDED,
    candidateCount = candidates.size,
    blockReason = null,
    blockedDetail = null,
    nextAttemptAt = null,
    providerLabel = "Ark Seedream",
    lockedProviderId = UUID.randomUUID(),
    garmentAssetId = UUID.randomUUID(),
    personAssetIds = listOf(UUID.randomUUID()),
    maskAssetId = null,
    relatedJobId = null,
    workflowLabel = null,
    candidates = candidates,
    createdAt = OffsetDateTime.now(),
    updatedAt = OffsetDateTime.now(),
)

class ResultLogicTest {
    @Test
    fun galleryIsOrderedByCandidateAndAttempt() {
        val second = candidate(1, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true)))
        val first = candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true)))
        val items = galleryItems(job(listOf(second, first)))
        assertEquals(listOf(0, 1), items.map { it.candidateIndex })
    }

    @Test
    fun traceableCandidatesExcludeSuccessfulOnes() {
        val succeeded = candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true)))
        val failed = candidate(1, CandidateStateDomain.FAILED)
        val cancelled = candidate(2, CandidateStateDomain.CANCELLED)
        val traceable = traceableCandidates(job(listOf(succeeded, failed, cancelled)))
        assertEquals(setOf(1, 2), traceable.map { it.candidateIndex }.toSet())
    }

    @Test
    fun firstAvailableOutputSkipsDeletedContent() {
        val deleted = output(false)
        val available = output(true)
        val target = job(
            listOf(
                candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(deleted, available)),
            ),
        )
        assertEquals(available.assetId, firstAvailableOutputAssetId(target))
        assertNull(firstAvailableOutputAssetId(job(listOf(candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(deleted))))))
    }

    @Test
    fun updateOutputReconcilesFavoriteAndAvailability() {
        val target = output(true)
        val source = job(listOf(candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(target))))
        val favorited = updateOutput(source, target.assetId) { it.copy(favorite = true) }
        assertTrue(galleryItems(favorited).first().output.favorite)
        val deleted = updateOutput(source, target.assetId) { it.copy(contentAvailable = false) }
        assertFalse(galleryItems(deleted).first().output.contentAvailable)
    }
}
