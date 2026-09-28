package com.clothesmodel.android.data

import java.util.UUID
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

private val problemMedia = "application/problem+json".toMediaType()

private fun problemBody(code: String, status: Int, context: String = "{}") = """
    {
      "type": "https://clothes-model.local/problems/$code",
      "title": "请求无法完成",
      "status": $status,
      "code": "$code",
      "detail": "测试详情。",
      "trace_id": "tr_test",
      "retryable": false,
      "field_errors": [],
      "context": $context
    }
""".trimIndent()

class DataMapperTest {
    @Test
    fun unknownWireValuesRemainSafe() {
        assertEquals(JobStateDomain.UNKNOWN, JobStateDomain.fromWire("future_state"))
        assertEquals(CandidateStateDomain.UNKNOWN, CandidateStateDomain.fromWire(null))
        assertEquals(BlockReasonDomain.UNKNOWN, BlockReasonDomain.fromWire("future_reason"))
        assertNull(BlockReasonDomain.fromWire(null))
        assertEquals(GarmentCategory.UNKNOWN, GarmentCategory.fromWire("cape"))
        assertEquals(GarmentSource.UNKNOWN, GarmentSource.fromWire("ai_generated"))
        assertEquals(ProviderAvailabilityDomain.UNKNOWN, ProviderAvailabilityDomain.fromWire("x"))
    }

    @Test
    fun terminalStatesAreRecognized() {
        assertTrue(JobStateDomain.FAILED.isTerminal)
        assertTrue(JobStateDomain.PARTIALLY_SUCCEEDED.isTerminal)
        assertFalse(JobStateDomain.RUNNING.isTerminal)
        assertTrue(CandidateStateDomain.CANCELLED.isTerminal)
        assertFalse(CandidateStateDomain.NEEDS_ATTENTION.isTerminal)
    }
}

class RefreshPolicyTest {
    @Test
    fun pollsOnlyNonTerminalNonAttentionStates() {
        assertTrue(RefreshPolicy.shouldPoll(JobStateDomain.RUNNING))
        assertTrue(RefreshPolicy.shouldPoll(JobStateDomain.WAITING_PROVIDER))
        assertFalse(RefreshPolicy.shouldPoll(JobStateDomain.NEEDS_ATTENTION))
        assertFalse(RefreshPolicy.shouldPoll(JobStateDomain.SUCCEEDED))
        assertFalse(RefreshPolicy.shouldPoll(JobStateDomain.UNKNOWN))
    }
}

class BoundedMemoryImageCacheTest {
    @Test
    fun evictsLeastRecentlyUsedWhenOverBudget() {
        val cache = BoundedMemoryImageCache(maxBytes = 6)
        val first = UUID.randomUUID()
        val second = UUID.randomUUID()
        val third = UUID.randomUUID()
        cache.put(first, ByteArray(4))
        cache.put(second, ByteArray(4))
        assertNull(cache.get(first))
        assertNotNull(cache.get(second))
        cache.get(second)
        cache.put(third, ByteArray(4))
        assertNull(cache.get(second))
        assertNotNull(cache.get(third))
    }

    @Test
    fun keysAreAssetIdentifiersNotCredentials() {
        val cache = BoundedMemoryImageCache(maxBytes = 1024)
        val assetId = UUID.randomUUID()
        cache.put(assetId, byteArrayOf(1, 2, 3))
        assertNotNull(cache.get(assetId))
        cache.evict(assetId)
        assertNull(cache.get(assetId))
    }
}

class AuthenticatedImageLoaderTest {
    private class RecordingFetcher(
        private val result: Outcome<ByteArray>,
    ) : ContentFetcher {
        var calls = 0
        override suspend fun fetch(assetId: UUID): Outcome<ByteArray> {
            calls += 1
            return result
        }
    }

    @Test
    fun cachesDownloadedBytesAndAvoidsSecondFetch() = runTest {
        val fetcher = RecordingFetcher(Outcome.Success(byteArrayOf(9, 9)))
        val loader = AuthenticatedImageLoader(fetcher)
        val assetId = UUID.randomUUID()

        val first = loader.load(assetId)
        val second = loader.load(assetId)

        assertTrue(first is ImageResult.Loaded)
        assertTrue(second is ImageResult.Loaded)
        assertEquals(1, fetcher.calls)
    }

    @Test
    fun missingContentMapsToDeletedPlaceholder() = runTest {
        val fetcher = RecordingFetcher(
            Outcome.Problem(ProblemModel("not_found", "素材内容不存在。", 404, false)),
        )
        val loader = AuthenticatedImageLoader(fetcher)
        assertEquals(ImageResult.DeletedContent, loader.load(UUID.randomUUID()))
    }

    @Test
    fun expiredAuthenticationPropagates() = runTest {
        val fetcher = RecordingFetcher(Outcome.AuthenticationExpired)
        val loader = AuthenticatedImageLoader(fetcher)
        assertEquals(ImageResult.AuthenticationExpired, loader.load(UUID.randomUUID()))
    }

    @Test
    fun evictionForcesRefetch() = runTest {
        val fetcher = RecordingFetcher(Outcome.Success(byteArrayOf(1)))
        val loader = AuthenticatedImageLoader(fetcher)
        val assetId = UUID.randomUUID()
        loader.load(assetId)
        loader.evict(assetId)
        loader.load(assetId)
        assertEquals(2, fetcher.calls)
    }
}

class ProblemParserTest {
    @Test
    fun parsesStructuredConflictContext() {
        val body = problemBody("asset_referenced", 409, context = """{"reference_count": 3}""")
            .toResponseBody(problemMedia)
        val problem = ProblemParser.from(body)
        assertEquals("asset_referenced", problem.code)
        assertEquals(409, problem.status)
        assertEquals(3, problem.referenceCount)
    }

    @Test
    fun malformedBodyFallsBackSafely() {
        val problem = ProblemParser.from("not-json".toResponseBody(problemMedia))
        assertEquals("request_failed", problem.code)
        assertTrue(problem.retryable)
    }
}

class RepositoryOutcomeTest {
    private class RecordingEvents : AuthenticationEvents {
        var expired = false
        override suspend fun onAuthenticationExpired() {
            expired = true
        }
    }

    @Test
    fun unauthorizedRoutesToAuthenticationExpired() = runTest {
        val events = RecordingEvents()
        val response = Response.error<String>(
            401,
            problemBody("authentication_required", 401).toResponseBody(problemMedia),
        )
        val outcome = response.toOutcome(events) { it }
        assertTrue(outcome is Outcome.AuthenticationExpired)
        assertTrue(events.expired)
    }

    @Test
    fun problemResponseMapsToProblem() = runTest {
        val events = RecordingEvents()
        val response = Response.error<String>(
            409,
            problemBody("provider_not_usable", 409).toResponseBody(problemMedia),
        )
        val outcome = response.toOutcome(events) { it }
        assertTrue(outcome is Outcome.Problem)
        assertEquals("provider_not_usable", (outcome as Outcome.Problem).problem.code)
        assertFalse(events.expired)
    }

    @Test
    fun successfulResponseTransformsBody() = runTest {
        val events = RecordingEvents()
        val response = Response.success("ready")
        val outcome = response.toOutcome(events) { it.uppercase() }
        assertEquals(Outcome.Success("READY"), outcome)
    }
}
