package com.clothesmodel.android.jobs

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.CandidateStateDomain
import com.clothesmodel.android.data.ContentFetcher
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobOutputModel
import com.clothesmodel.android.data.JobStateDomain
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.ui.theme.ClothesModelTheme
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Rule
import org.junit.Test

class JobDetailScreenTest {
    @get:Rule
    val rule = createComposeRule()

    private val loader = AuthenticatedImageLoader(
        ContentFetcher { Outcome.Problem(ProblemModel("not_found", "不可用", 404, false)) },
    )

    private fun output(available: Boolean) = JobOutputModel(
        id = UUID.randomUUID(),
        jobItemId = UUID.randomUUID(),
        assetId = UUID.randomUUID(),
        favorite = false,
        contentAvailable = available,
        seed = null,
        createdAt = OffsetDateTime.now(),
    )

    private fun candidate(
        state: CandidateStateDomain,
        attempt: Int = 1,
        outputs: List<JobOutputModel> = emptyList(),
    ) = CandidateModel(
        id = UUID.randomUUID(),
        jobId = UUID.randomUUID(),
        candidateIndex = 0,
        state = state,
        attempt = attempt,
        blockReason = null,
        retryOfJobItemId = null,
        supersededByJobItemId = null,
        externalExecutionId = "exec-123",
        nextAttemptAt = null,
        outputs = outputs,
        errorCode = null,
        errorDetail = null,
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    private fun job(state: JobStateDomain, candidates: List<CandidateModel>) = JobModel(
        id = UUID.randomUUID(),
        state = state,
        candidateCount = candidates.size,
        blockReason = null,
        blockedDetail = null,
        nextAttemptAt = null,
        providerLabel = "Ark Seedream",
        lockedProviderId = UUID.randomUUID(),
        garmentAssetId = UUID.randomUUID(),
        maskAssetId = null,
        relatedJobId = null,
        workflowLabel = null,
        candidates = candidates,
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    private fun render(state: JobDetailUiState) {
        rule.setContent {
            ClothesModelTheme {
                JobDetailScreen(
                    state = state,
                    imageLoader = loader,
                    jobId = "job",
                    onBack = {},
                    onOpenResults = {},
                    onCancelJob = {},
                    onCancelCandidate = {},
                    onRetryCandidate = {},
                    onRequeryCandidate = {},
                    onFinishFailed = { _, _ -> },
                    onConfirmRetry = {},
                    onDismissRetry = {},
                    onDismissCommandError = {},
                )
            }
        }
    }

    @Test
    fun needsAttentionCandidateExposesThreeRecoveryActions() {
        render(
            JobDetailUiState(
                loading = false,
                job = job(JobStateDomain.NEEDS_ATTENTION, listOf(candidate(CandidateStateDomain.NEEDS_ATTENTION))),
            ),
        )
        rule.onNodeWithText("重新查询").assertIsDisplayed()
        rule.onNodeWithText("明确重试").assertIsDisplayed()
        rule.onNodeWithText("结束失败").assertIsDisplayed()
    }

    @Test
    fun terminalJobHasNoCancelButShowsResults() {
        render(
            JobDetailUiState(
                loading = false,
                job = job(JobStateDomain.SUCCEEDED, listOf(candidate(CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true))))),
            ),
        )
        rule.onNodeWithText("查看结果").assertIsDisplayed()
        rule.onNodeWithText("取消任务").assertDoesNotExist()
    }

    @Test
    fun lineageIsProgressiveDisclosure() {
        render(
            JobDetailUiState(
                loading = false,
                job = job(JobStateDomain.FAILED, listOf(candidate(CandidateStateDomain.FAILED, attempt = 2))),
            ),
        )
        rule.onNodeWithText("展开执行谱系").performClick()
        rule.onNodeWithText("尝试次数：2").assertIsDisplayed()
        rule.onNodeWithText("外部执行标识：exec-123").assertIsDisplayed()
    }

    @Test
    fun runningJobShowsStageElapsedAndCompletedCandidateCount() {
        val syncedAt = OffsetDateTime.parse("2026-09-30T12:34:56+08:00")
        render(
            JobDetailUiState(
                loading = false,
                lastSyncedAt = syncedAt,
                job = job(
                    JobStateDomain.RUNNING,
                    listOf(
                        candidate(CandidateStateDomain.SUCCEEDED),
                        candidate(CandidateStateDomain.RUNNING),
                    ),
                ),
            ),
        )
        rule.onNodeWithText("阶段 3/3 · 正在生成").assertIsDisplayed()
        rule.onNodeWithText("当前 Provider 不提供百分比，进度按执行阶段显示。").assertIsDisplayed()
        rule.onNodeWithText("已完成 1/2 · 成功 1 · 失败 0").assertIsDisplayed()
        rule.onNodeWithText("最后更新 12:34:56").assertIsDisplayed()
    }

    @Test
    fun staleJobKeepsLastProgressAndExplainsRecovery() {
        render(
            JobDetailUiState(
                loading = false,
                stale = true,
                job = job(JobStateDomain.WAITING_PROVIDER, listOf(candidate(CandidateStateDomain.WAITING_PROVIDER))),
            ),
        )
        rule.onNodeWithText("等待 Provider · 恢复后自动继续").assertIsDisplayed()
        rule.onNodeWithText("连接异常，当前显示上一次同步结果；网络恢复后会自动刷新。").assertIsDisplayed()
    }
}
