package com.clothesmodel.android.contractstatus

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import org.junit.Rule
import org.junit.Test

class ContractStatusScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun rendersContractProbeContent() {
        composeRule.setContent {
            ClothesModelTheme {
                ContractStatusScreen(
                    state = ContractStatusUiState.Content(
                        ContractStatusSnapshot(
                            probes = listOf(
                                ContractProbe("Health", "ok", successful = true),
                            ),
                        ),
                    ),
                    onRefresh = {},
                )
            }
        }

        composeRule.onNodeWithText("Generated client boundary").assertIsDisplayed()
        composeRule.onNodeWithText("Health").assertIsDisplayed()
        composeRule.onNodeWithText("ok").assertIsDisplayed()
    }
}
