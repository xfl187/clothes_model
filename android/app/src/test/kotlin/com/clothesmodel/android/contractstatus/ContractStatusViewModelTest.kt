package com.clothesmodel.android.contractstatus

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ContractStatusViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun `loads gateway snapshot into content state`() = runTest(mainDispatcherRule.dispatcher) {
        val expected = ContractStatusSnapshot(
            probes = listOf(ContractProbe("Health", "ok", successful = true)),
        )
        val viewModel = ContractStatusViewModel(
            gateway = object : ContractStatusGateway {
                override suspend fun loadStatus() = expected
            },
        )

        testScheduler.advanceUntilIdle()

        assertEquals(ContractStatusUiState.Content(expected), viewModel.state.value)
    }
}
