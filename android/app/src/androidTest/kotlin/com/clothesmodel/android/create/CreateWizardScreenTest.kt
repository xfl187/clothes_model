package com.clothesmodel.android.create

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.AssetLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.ContentFetcher
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import java.time.OffsetDateTime
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
                    onImport = {},
                    onRetryImport = {},
                    onCancelImport = {},
                )
            }
        }
    }

    @Test
    fun personStepExplainsMissingAssets() {
        render(CreateWizardUiState(step = WizardStep.PERSON, assetsLoading = false))
        rule.onNodeWithText("第 1 步：选择人物").assertIsDisplayed()
        rule.onNodeWithText("从相册导入人物").assertIsDisplayed()
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

    @Test
    fun selectedAssetKeepsPrimaryActionVisible() {
        val asset = AssetModel(
            id = UUID.fromString("497f6eca-6276-4993-bfeb-53cbbbba6f08"),
            kind = "person",
            favorite = false,
            lifecycle = AssetLifecycle.ACTIVE,
            contentAvailable = true,
            width = 1024,
            height = 1536,
            createdAt = OffsetDateTime.parse("2019-08-24T14:15:22Z"),
            garmentCategory = null,
            garmentSource = null,
            qualityWarnings = emptyList(),
        )
        render(
            CreateWizardUiState(
                step = WizardStep.PERSON,
                personAsset = asset,
                assets = listOf(asset),
                assetsLoading = false,
            ),
        )

        rule.onNodeWithText("已选择 ·", substring = true).assertIsDisplayed()
        rule.onNodeWithText("下一步").assertIsDisplayed()
    }

    @Test
    fun settingsStepExplainsWhyGenerationIsDisabled() {
        render(
            CreateWizardUiState(
                step = WizardStep.SETTINGS,
                loading = false,
                providers = listOf(
                    ProviderModel(
                        id = UUID.randomUUID(),
                        displayName = "Ark Seedream",
                        availability = ProviderAvailabilityDomain.UNAVAILABLE_CONFIGURATION,
                        isDefault = true,
                        maxCandidates = 1,
                        supportsManualMask = false,
                        supportsRegionMask = false,
                        garmentCategories = emptyList(),
                        unavailableReason = "Provider 凭据无法解密，请管理员重新保存 API Key。",
                    ),
                ),
            ),
        )

        rule.onAllNodesWithText(
            "Provider 凭据无法解密，请管理员重新保存 API Key。",
            substring = true,
        ).assertCountEquals(2)
        rule.onNodeWithText("重新检查").assertIsDisplayed()
        rule.onNodeWithText("暂不可用").assertIsDisplayed()
    }

    @Test
    fun garmentStepOffersInlineImport() {
        render(CreateWizardUiState(step = WizardStep.GARMENT, assetsLoading = false))

        rule.onNodeWithText("第 2 步：选择衣物").assertIsDisplayed()
        rule.onNodeWithText("从相册导入衣物").assertIsDisplayed()
    }
}
