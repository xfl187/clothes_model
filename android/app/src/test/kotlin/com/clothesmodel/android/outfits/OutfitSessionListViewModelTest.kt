package com.clothesmodel.android.outfits

import com.clothesmodel.android.contractstatus.MainDispatcherRule
import com.clothesmodel.android.data.ApiServicesFactory
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticationEvents
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.OutfitRepository
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.contract.model.LayerRole
import com.clothesmodel.contract.model.OutfitLayerResult
import com.clothesmodel.contract.model.OutfitRoute
import com.clothesmodel.contract.model.OutfitSession
import com.clothesmodel.contract.model.RemoveOutfitLayerRequest
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class OutfitSessionListViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private fun session(id: UUID, name: String, favorite: Boolean = false) = OutfitSession(
        id = id,
        name = name,
        favorite = favorite,
        personAssetId = UUID.randomUUID(),
        layerDefinitionVersion = 1,
        layerTypes = emptyList(),
        branches = emptyList(),
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    private fun emptyAssetRepository(): AssetRepository = AssetRepository(
        factory = object : ApiServicesFactory {
            override suspend fun services() = null
        },
        events = object : AuthenticationEvents {
            override suspend fun onAuthenticationExpired() = Unit
        },
    )

    private open class FakeOutfitRepository(
        private val sessions: List<OutfitSession>,
        private val created: OutfitSession?,
    ) : OutfitRepository {
        override suspend fun list(limit: Int) = Outcome.Success(sessions)

        override suspend fun create(
            personAssetId: UUID,
            name: String?,
            idempotencyKey: String,
        ) = created?.let { Outcome.Success(it) }
            ?: Outcome.Problem(ProblemModel("not_found", "", 0, false))

        override suspend fun setFavorite(sessionId: UUID, favorite: Boolean): Outcome<OutfitSession> {
            val current = sessions.first { it.id == sessionId }
            return Outcome.Success(current.copy(favorite = favorite))
        }

        override suspend fun get(sessionId: UUID): Outcome<OutfitSession> =
            Outcome.Success(sessions.first { it.id == sessionId })

        override suspend fun addLayer(
            sessionId: UUID,
            branchId: UUID,
            role: LayerRole,
            garmentAssetId: UUID,
            providerId: UUID?,
            candidateCount: Int,
            idempotencyKey: String,
        ): Outcome<OutfitLayerResult> = throw UnsupportedOperationException()

        override suspend fun selectRevision(
            sessionId: UUID,
            branchId: UUID,
            revisionId: UUID,
            jobItemId: UUID,
            outputId: UUID,
            idempotencyKey: String,
        ): Outcome<OutfitSession> = throw UnsupportedOperationException()

        override suspend fun removeLayer(
            sessionId: UUID,
            branchId: UUID,
            layerId: UUID,
            mode: RemoveOutfitLayerRequest.Mode?,
        ): Outcome<OutfitSession> = throw UnsupportedOperationException()

        override suspend fun switchRoute(
            sessionId: UUID,
            route: OutfitRoute,
            idempotencyKey: String,
        ): Outcome<OutfitSession> = throw UnsupportedOperationException()
    }

    @Test
    fun `refresh loads sessions`() = runTest(mainDispatcherRule.dispatcher) {
        val expected = listOf(session(UUID.randomUUID(), "Look A"))
        val viewModel = OutfitSessionListViewModel(
            FakeOutfitRepository(expected, expected.first()),
            emptyAssetRepository(),
        )

        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertEquals(expected, viewModel.state.value.sessions)
        assertFalse(viewModel.state.value.loading)
    }

    @Test
    fun `create exposes the new session`() = runTest(mainDispatcherRule.dispatcher) {
        val created = session(UUID.randomUUID(), "New Look")
        val viewModel = OutfitSessionListViewModel(
            FakeOutfitRepository(emptyList(), created),
            emptyAssetRepository(),
        )
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        viewModel.create(UUID.randomUUID())
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertEquals(created, viewModel.state.value.createdSession)
        assertFalse(viewModel.state.value.creating)
    }

    @Test
    fun `toggleFavorite updates the matching session`() = runTest(mainDispatcherRule.dispatcher) {
        val initial = session(UUID.randomUUID(), "Look A", favorite = false)
        val viewModel = OutfitSessionListViewModel(
            FakeOutfitRepository(listOf(initial), initial),
            emptyAssetRepository(),
        )
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        viewModel.toggleFavorite(initial)
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.state.value.sessions.single().favorite)
    }
}
