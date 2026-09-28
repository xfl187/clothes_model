package com.clothesmodel.android.jobs

import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.CandidateStateDomain
import com.clothesmodel.android.data.JobStateDomain
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private fun candidate(state: CandidateStateDomain, attempt: Int = 1, index: Int = 0) =
    CandidateModel(
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
        outputs = emptyList(),
        errorCode = null,
        errorDetail = null,
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

class JobDetailLogicTest {
    @Test
    fun cancelIsAvailableOnlyForNonTerminalWork() {
        assertTrue(canCancelJob(JobStateDomain.RUNNING))
        assertTrue(canCancelJob(JobStateDomain.NEEDS_ATTENTION))
        assertFalse(canCancelJob(JobStateDomain.SUCCEEDED))
        assertFalse(canCancelJob(JobStateDomain.PARTIALLY_SUCCEEDED))
        assertFalse(canCancelJob(JobStateDomain.CANCELLED))

        assertTrue(canCancelCandidate(CandidateStateDomain.QUEUED))
        assertFalse(canCancelCandidate(CandidateStateDomain.CANCELLED))
    }

    @Test
    fun retryAndAttentionActionsAreStateSpecific() {
        assertTrue(canRetryCandidate(CandidateStateDomain.FAILED))
        assertFalse(canRetryCandidate(CandidateStateDomain.NEEDS_ATTENTION))
        assertFalse(canRetryCandidate(CandidateStateDomain.SUCCEEDED))

        assertTrue(needsAttentionActions(CandidateStateDomain.NEEDS_ATTENTION))
        assertFalse(needsAttentionActions(CandidateStateDomain.FAILED))
    }

    @Test
    fun candidateLabelsCoverEveryState() {
        assertEquals("已排队", candidateStateLabel(CandidateStateDomain.QUEUED))
        assertEquals("等待 Provider", candidateStateLabel(CandidateStateDomain.WAITING_PROVIDER))
        assertEquals("需要人工处理", candidateStateLabel(CandidateStateDomain.NEEDS_ATTENTION))
        assertEquals("成功", candidateStateLabel(CandidateStateDomain.SUCCEEDED))
        assertEquals("已取消", candidateStateLabel(CandidateStateDomain.CANCELLED))
        assertEquals("状态未知", candidateStateLabel(CandidateStateDomain.UNKNOWN))
    }

    @Test
    fun countsSplitPartialSuccess() {
        val candidates = listOf(
            candidate(CandidateStateDomain.SUCCEEDED, index = 0),
            candidate(CandidateStateDomain.FAILED, index = 1),
            candidate(CandidateStateDomain.RUNNING, index = 2),
        )
        assertEquals(1, succeededCandidates(candidates))
        assertEquals(1, failedCandidates(candidates))
    }

    @Test
    fun elapsedTimeIsReadable() {
        val start = OffsetDateTime.parse("2026-09-28T12:00:00Z")
        assertEquals("5 分钟", formatElapsed(start, start.plusMinutes(5)))
        assertEquals("2 小时 3 分", formatElapsed(start, start.plusMinutes(123)))
    }
}
