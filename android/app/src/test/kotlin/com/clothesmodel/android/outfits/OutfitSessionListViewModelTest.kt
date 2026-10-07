package com.clothesmodel.android.outfits

import com.clothesmodel.android.contractstatus.MainDispatcherRule
import com.clothesmodel.android.data.ApiServicesFactory
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticationEvents
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.OutfitRepository
import com.clothesmodel.contract.model.OutfitSession
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

    @Test
    fun `refresh loads sessions`() = runTest(mainDispatcherRule.dispatcher) {
        val expected = listOf(session(UUID.randomUUID(), "Look A"))
        val repository = object : OutfitRepository {
            override suspend fun list(limit: Int) = Outcome.Success(expected)
            override suspend fun create(personAssetId: UUID, name: String?, idempotencyKey: String) =
                Outcome.Success(expected.first())

            override suspend fun setFavorite(sessionId: UUID, favorite: Boolean) =
                Outcome.Success(expected.first())
        }
        val viewModel = OutfitSessionListViewModel(repository, emptyAssetRepository())

        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertEquals(expected, viewModel.state.value.sessions)
        assertFalse(viewModel.state.value.loading)
    }

    @Test
    fun `create exposes the new session`() = runTest(mainDispatcherRule.dispatcher) {
        val created = session(UUID.randomUUID(), "New Look")
        val repository = object : OutfitRepository {
            override suspend fun list(limit: Int) = Outcome.Success(emptyList<OutfitSession>())
            override suspend fun create(personAssetId: UUID, name: String?, idempotencyKey: String) =
                Outcome.Success(created)

            override suspend fun setFavorite(sessionId: UUID, favorite: Boolean) =
                Outcome.Success(created)
        }
        val viewModel = OutfitSessionListViewModel(repository, emptyAssetRepository())
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        viewModel.create(UUID.randomUUID())
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertEquals(created, viewModel.state.value.createdSession)
        assertFalse(viewModel.state.value.creating)
    }

    @Test
    fun `toggleFavorite updates the matching session`() = runTest(mainDispatcherRule.dispatcher) {
        val id = UUID.randomUUID()
        val initial = session(id, "Look A", favorite = false)
        val repository = object : OutfitRepository {
            override suspend fun list(limit: Int) = Outcome.Success(listOf(initial))
            override suspend fun create(personAssetId: UUID, name: String?, idempotencyKey: String) =
                Outcome.Success(initial)

            override suspend fun setFavorite(sessionId: UUID, favorite: Boolean) =
                Outcome.Success(initial.copy(favorite = favorite))
        }
        val viewModel = OutfitSessionListViewModel(repository, emptyAssetRepository())
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        viewModel.toggleFavorite(initial)
        mainDispatcherRule.dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.state.value.sessions.single().favorite)
    }
}
