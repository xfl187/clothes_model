package com.clothesmodel.android.assets

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AssetCenterLogicTest {
    @Test
    fun gridFallsBackToWiderCellsUnderLargeFont() {
        assertEquals(148.dp, gridMinSizeDp(1.0f))
        assertEquals(200.dp, gridMinSizeDp(1.4f))
        assertEquals(320.dp, gridMinSizeDp(2.0f))
        assertTrue(gridMinSizeDp(2.0f) > gridMinSizeDp(1.0f))
    }

    @Test
    fun importStatusExplainsProgressAndFailure() {
        val uploading = PendingImportUi(
            id = "1",
            displayName = "人物图片",
            state = "uploading",
            uploadedBytes = 10,
            totalBytes = 100,
            error = null,
            assetId = null,
        )
        assertEquals("正在上传 10/100", importStatusLabel(uploading))

        val failed = uploading.copy(state = "failed", error = "网络不可用。")
        assertEquals("网络不可用。", importStatusLabel(failed))
        assertTrue(failed.failed)

        val staged = uploading.copy(state = "staged")
        assertEquals("等待上传", importStatusLabel(staged))
    }
}
