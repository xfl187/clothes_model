package com.clothesmodel.android.assets

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.AssetLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.ContentFetcher
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class AssetCenterScreenTest {
    @get:Rule
    val rule = createComposeRule()

    private val loader = AuthenticatedImageLoader(
        ContentFetcher { Outcome.Problem(ProblemModel("not_found", "不可用", 404, false)) },
    )

    private fun setScreen(
        state: AssetCenterUiState,
        onSegment: (AssetSegment) -> Unit = {},
    ) {
        rule.setContent {
            ClothesModelTheme {
                AssetCenterScreen(
                    state = state,
                    imageLoader = loader,
                    onSegment = onSegment,
                    onCategory = {},
                    onImport = { _, _, _ -> },
                    onRetryImport = {},
                    onCancelImport = {},
                    onToggleFavorite = {},
                    onRefresh = {},
                    onLoadMore = {},
                    onOpenAsset = {},
                    onCreate = {},
                )
            }
        }
    }

    @Test
    fun emptyLibraryExplainsNextStep() {
        setScreen(AssetCenterUiState(loading = false))
        rule.onNodeWithText("还没有素材").assertIsDisplayed()
        rule.onNodeWithText("导入人物图片").assertIsDisplayed()
    }

    @Test
    fun garmentSegmentOffersCategoryFilters() {
        setScreen(AssetCenterUiState(loading = false, segment = AssetSegment.GARMENT))
        rule.onNodeWithText("上装").assertIsDisplayed()
        rule.onNodeWithText("下装").assertIsDisplayed()
        rule.onNodeWithText("连衣裙").assertIsDisplayed()
    }

    @Test
    fun segmentSelectionIsReported() {
        var selected: AssetSegment? = null
        setScreen(AssetCenterUiState(loading = false)) { selected = it }
        rule.onNodeWithText("衣物").performClick()
        assertEquals(AssetSegment.GARMENT, selected)
    }

    @Test
    fun inProgressImportOffersCancel() {
        setScreen(
            AssetCenterUiState(
                loading = false,
                imports = listOf(
                    PendingImportUi(
                        id = "1",
                        displayName = "人物图片",
                        state = "uploading",
                        uploadedBytes = 0,
                        totalBytes = 10,
                        error = null,
                        assetId = null,
                    ),
                ),
            ),
        )
        rule.onNodeWithText("正在导入").assertIsDisplayed()
        rule.onNodeWithText("取消导入").assertIsDisplayed()
    }

    @Test
    fun deletedAssetsAreNotShownInReusableLibrary() {
        val deleted = AssetModel(
            id = UUID.randomUUID(),
            kind = "person",
            favorite = false,
            lifecycle = AssetLifecycle.DELETED_CONTENT,
            contentAvailable = false,
            width = 100,
            height = 100,
            createdAt = OffsetDateTime.now(),
            garmentCategory = null,
            garmentSource = null,
            qualityWarnings = emptyList(),
        )

        setScreen(AssetCenterUiState(loading = false, assets = listOf(deleted)))

        rule.onNodeWithText("素材已删除").assertDoesNotExist()
        rule.onNodeWithText("还没有素材").assertIsDisplayed()
    }
}
