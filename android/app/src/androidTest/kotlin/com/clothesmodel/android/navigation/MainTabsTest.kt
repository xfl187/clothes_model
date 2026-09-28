package com.clothesmodel.android.navigation

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import org.junit.Rule
import org.junit.Test

class MainTabsTest {
    @get:Rule
    val rule = createComposeRule()

    private fun setTabs() {
        rule.setContent {
            ClothesModelTheme {
                MainTabs(onCreate = {}, onOpenAsset = {}, onOpenJob = {})
            }
        }
    }

    @Test
    fun showsFixedThreeTabNavigation() {
        setTabs()
        rule.onNodeWithText("首页").assertIsDisplayed()
        rule.onNodeWithText("素材").assertIsDisplayed()
        rule.onNodeWithText("历史").assertIsDisplayed()
    }

    @Test
    fun switchingTabsShowsEachDestination() {
        setTabs()
        rule.onNodeWithText("素材").performClick()
        rule.onNodeWithText("人物与衣物素材库将在此显示。").assertIsDisplayed()

        rule.onNodeWithText("历史").performClick()
        rule.onNodeWithText("全部任务状态将在此显示。").assertIsDisplayed()
    }

    @Test
    fun homeOffersPrimaryTryOnEntry() {
        setTabs()
        rule.onNodeWithText("开始精准换装").assertIsDisplayed()
    }
}
