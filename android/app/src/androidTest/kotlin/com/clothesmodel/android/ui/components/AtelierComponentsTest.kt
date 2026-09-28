package com.clothesmodel.android.ui.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.clothesmodel.android.ui.theme.AtelierStatus
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import org.junit.Rule
import org.junit.Test

class AtelierComponentsTest {
    @get:Rule
    val rule = createComposeRule()

    @Test
    fun statusMarkerConveysStateWithTextNotColorAlone() {
        rule.setContent {
            ClothesModelTheme {
                StatusMarker(status = AtelierStatus.WAITING_PROVIDER, label = "等待 Provider")
            }
        }
        rule.onNodeWithText("等待 Provider").assertIsDisplayed()
    }

    @Test
    fun deletedContentPlaceholderIsLabelled() {
        rule.setContent {
            ClothesModelTheme {
                DeletedContentPlaceholder(label = "素材已删除")
            }
        }
        rule.onNodeWithText("素材已删除").assertIsDisplayed()
    }

    @Test
    fun emptyStateExposesNextAction() {
        rule.setContent {
            ClothesModelTheme {
                EmptyState(
                    title = "暂无素材",
                    message = "先导入一张人物图片。",
                    actionLabel = "导入",
                    onAction = {},
                )
            }
        }
        rule.onNodeWithText("暂无素材").assertIsDisplayed()
        rule.onNodeWithText("导入").assertIsDisplayed()
    }
}
