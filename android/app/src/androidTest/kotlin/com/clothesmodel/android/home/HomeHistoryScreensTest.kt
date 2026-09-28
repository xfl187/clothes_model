package com.clothesmodel.android.home

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.ContentFetcher
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobStateDomain
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.history.HistoryScreen
import com.clothesmodel.android.history.HistoryUiState
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Rule
import org.junit.Test

class HomeHistoryScreensTest {
    @get:Rule
    val rule = createComposeRule()

    private val loader = AuthenticatedImageLoader(
        ContentFetcher { Outcome.Problem(ProblemModel("not_found", "不可用", 404, false)) },
    )

    private fun job(state: JobStateDomain): JobModel = JobModel(
        id = UUID.randomUUID(),
        state = state,
        candidateCount = 1,
        blockReason = null,
        blockedDetail = null,
        nextAttemptAt = null,
        providerLabel = "Ark Seedream",
        maskAssetId = null,
        relatedJobId = null,
        workflowLabel = null,
        candidates = emptyList(),
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    @Test
    fun homeShowsPrimaryEntryAndComingSoon() {
        rule.setContent {
            ClothesModelTheme {
                HomeScreen(
                    state = HomeUiState(loading = false),
                    imageLoader = loader,
                    onCreate = {},
                    onOpenJob = {},
                    onRefresh = {},
                )
            }
        }
        rule.onNodeWithText("开始精准换装").assertIsDisplayed()
        rule.onNodeWithText("分层穿搭").assertIsDisplayed()
        rule.onNodeWithText("创意写真").assertIsDisplayed()
    }

    @Test
    fun historyDistinguishesEveryAggregateState() {
        rule.setContent {
            ClothesModelTheme {
                HistoryScreen(
                    state = HistoryUiState(
                        loading = false,
                        jobs = listOf(
                            job(JobStateDomain.WAITING_PROVIDER),
                            job(JobStateDomain.PARTIALLY_SUCCEEDED),
                            job(JobStateDomain.NEEDS_ATTENTION),
                            job(JobStateDomain.CANCELLED),
                        ),
                    ),
                    imageLoader = loader,
                    onOpenJob = {},
                    onRefresh = {},
                    onLoadMore = {},
                )
            }
        }
        rule.onNodeWithText("等待 Provider，恢复后自动继续").assertIsDisplayed()
        rule.onNodeWithText("部分候选成功").assertIsDisplayed()
        rule.onNodeWithText("结果状态不确定，需要处理").assertIsDisplayed()
        rule.onNodeWithText("已取消").assertIsDisplayed()
    }

    @Test
    fun historyEmptyExplainsNextStep() {
        rule.setContent {
            ClothesModelTheme {
                HistoryScreen(
                    state = HistoryUiState(loading = false),
                    imageLoader = loader,
                    onOpenJob = {},
                    onRefresh = {},
                    onLoadMore = {},
                )
            }
        }
        rule.onNodeWithText("还没有任务").assertIsDisplayed()
    }
}
