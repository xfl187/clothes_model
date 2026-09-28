package com.clothesmodel.android.create

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.ContentFetcher
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import java.util.UUID
import org.junit.Rule
import org.junit.Test

class CreateWizardScreenTest {
    @get:Rule
    val rule = createComposeRule()

    private val loader = AuthenticatedImageLoader(
        ContentFetcher { Outcome.Problem(ProblemModel("not_found", "不可用", 404, false)) },
    )

    private fun render(state: CreateWizardUiState) {
        rule.setContent {
            ClothesModelTheme {
                CreateWizardScreen(
                    state = state,
                    imageLoader = loader,
                    onBack = {},
                    onNext = {},
                    onPrevious = {},
                    onSelectPerson = {},
                    onSelectGarment = {},
                    onCategory = {},
                    onSelectProvider = {},
                    onCandidateCount = {},
                    onSubmit = {},
                    onOpenAssets = {},
                )
            }
        }
    }

    @Test
    fun personStepExplainsMissingAssets() {
        render(CreateWizardUiState(step = WizardStep.PERSON, assetsLoading = false))
        rule.onNodeWithText("第 1 步：选择人物").assertIsDisplayed()
        rule.onNodeWithText("还没有可用素材").assertIsDisplayed()
    }

    @Test
    fun settingsStepShowsProviderAndCandidateCount() {
        render(
            CreateWizardUiState(
                step = WizardStep.SETTINGS,
                assetsLoading = false,
                providerId = null,
                providers = listOf(
                    ProviderModel(
                        id = UUID.randomUUID(),
                        displayName = "Ark Seedream",
                        availability = ProviderAvailabilityDomain.AVAILABLE,
                        isDefault = true,
                        maxCandidates = 2,
                        supportsManualMask = false,
                        supportsRegionMask = false,
                        garmentCategories = emptyList(),
                        unavailableReason = null,
                    ),
                ),
            ),
        )
        rule.onNodeWithText("Ark Seedream").assertIsDisplayed()
        rule.onNodeWithText("1 张").assertIsDisplayed()
    }
}
