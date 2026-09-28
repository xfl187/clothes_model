package com.clothesmodel.android.mask

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
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

class MaskEditorScreenTest {
    @get:Rule
    val rule = createComposeRule()

    private val loader = AuthenticatedImageLoader(
        ContentFetcher { Outcome.Problem(ProblemModel("not_found", "不可用", 404, false)) },
    )

    private fun render(state: MaskEditorUiState) {
        rule.setContent {
            ClothesModelTheme {
                MaskEditorScreen(
                    state = state,
                    imageLoader = loader,
                    onBack = {},
                    onTool = {},
                    onRadius = {},
                    onTogglePreview = {},
                    onStart = {},
                    onExtend = {},
                    onStrokeEnd = {},
                    onUndo = {},
                    onClear = {},
                    onSelectProvider = {},
                    onSubmit = {},
                )
            }
        }
    }

    @Test
    fun toolsAndUndoVisibilityFollowState() {
        render(
            MaskEditorUiState(
                loading = false,
                sourceAssetId = UUID.randomUUID(),
                sourceWidth = 400,
                sourceHeight = 600,
            ),
        )
        rule.onNodeWithText("画笔").assertIsDisplayed()
        rule.onNodeWithText("擦除").assertIsDisplayed()
        rule.onNodeWithText("撤销").assertIsNotEnabled()
        rule.onNodeWithText("清空").assertIsNotEnabled()
    }

    @Test
    fun drawnDocumentEnablesUndoAndSubmit() {
        val document = MaskDocument().startStroke(MaskTool.DRAW, 0.08f, MaskPoint(0.4f, 0.4f))
        render(
            MaskEditorUiState(
                loading = false,
                document = document,
                sourceAssetId = UUID.randomUUID(),
                sourceWidth = 400,
                sourceHeight = 600,
                selectedProviderId = UUID.randomUUID(),
            ),
        )
        rule.onNodeWithText("撤销").assertIsEnabled()
        rule.onNodeWithText("修正后重新生成").assertIsEnabled()
    }

    @Test
    fun providerSwitchIsExplicitWhenLockedProviderUnsupported() {
        render(
            MaskEditorUiState(
                loading = false,
                sourceAssetId = UUID.randomUUID(),
                sourceWidth = 400,
                sourceHeight = 600,
                providerNote = "原 Provider 不支持或暂不可用手动遮罩，请选择兼容 Provider 后再提交。",
                providers = listOf(
                    ProviderModel(
                        id = UUID.randomUUID(),
                        displayName = "Comfy Manual Mask",
                        availability = ProviderAvailabilityDomain.AVAILABLE,
                        isDefault = false,
                        maxCandidates = 1,
                        supportsManualMask = true,
                        supportsRegionMask = true,
                        garmentCategories = emptyList(),
                        unavailableReason = null,
                    ),
                ),
            ),
        )
        rule.onNodeWithText("原 Provider 不支持或暂不可用手动遮罩，请选择兼容 Provider 后再提交。")
            .assertIsDisplayed()
        rule.onNodeWithText("Comfy Manual Mask").assertIsDisplayed()
    }
}
