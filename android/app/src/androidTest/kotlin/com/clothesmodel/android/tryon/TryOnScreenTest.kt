package com.clothesmodel.android.tryon

import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class TryOnScreenTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun generationRequiresUploadedAssetsAndShowsServerState() {
        compose.setContent {
            TryOnScreen(
                state = TryOnUiState(jobId = "job-1", jobState = "running"),
                onPersonSelected = {},
                onGarmentSelected = {},
                onCategorySelected = {},
                onGenerate = {},
            )
        }
        compose.onNodeWithText("生成一张试穿图").assertIsNotEnabled()
        compose.onNodeWithText("正在生成，离开页面也会继续").assertExists()

        compose.setContent {
            TryOnScreen(
                state = TryOnUiState(
                    person = UploadSelection("p", "completed", "person-asset"),
                    garment = UploadSelection("g", "completed", "garment-asset"),
                ),
                onPersonSelected = {},
                onGarmentSelected = {},
                onCategorySelected = {},
                onGenerate = {},
            )
        }
        compose.onNodeWithText("生成一张试穿图").assertIsEnabled()
    }
}
