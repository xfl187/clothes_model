package com.clothesmodel.android.results

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
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

class ResultScreenTest {
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
        index: Int,
        state: CandidateStateDomain,
        outputs: List<JobOutputModel> = emptyList(),
    ) = CandidateModel(
        id = UUID.randomUUID(),
        jobId = UUID.randomUUID(),
        candidateIndex = index,
        state = state,
        attempt = 1,
        blockReason = null,
        retryOfJobItemId = null,
        supersededByJobItemId = null,
        externalExecutionId = null,
        nextAttemptAt = null,
        outputs = outputs,
        errorCode = null,
        errorDetail = null,
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    private fun job(candidates: List<CandidateModel>) = JobModel(
        id = UUID.randomUUID(),
        state = JobStateDomain.PARTIALLY_SUCCEEDED,
        candidateCount = candidates.size,
        blockReason = null,
        blockedDetail = null,
        nextAttemptAt = null,
        providerLabel = "Ark Seedream",
        lockedProviderId = UUID.randomUUID(),
        garmentAssetId = UUID.randomUUID(),
        personAssetIds = listOf(UUID.randomUUID()),
        maskAssetId = null,
        relatedJobId = null,
        workflowLabel = null,
        candidates = candidates,
        createdAt = OffsetDateTime.now(),
        updatedAt = OffsetDateTime.now(),
    )

    private fun render(state: ResultUiState) {
        rule.setContent {
            ClothesModelTheme {
                ResultScreen(
                    state = state,
                    imageLoader = loader,
                    onBack = {},
                    onSelect = {},
                    onFavorite = {},
                    onDownload = {},
                    onShare = {},
                    onDelete = {},
                    onRetryCandidate = {},
                    onCompare = {},
                    onMask = {},
                    onDismissConflict = {},
                    onDismissMessage = {},
                )
            }
        }
    }

    @Test
    fun selectedResultExposesAllContentOperations() {
        val success = candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true)))
        val failed = candidate(1, CandidateStateDomain.FAILED)
        render(
            ResultUiState(
                loading = false,
                job = job(listOf(success, failed)),
                selectedAssetId = success.outputs.first().assetId,
            ),
        )
        rule.onNodeWithText("下载").assertIsDisplayed()
        rule.onNodeWithText("分享").assertIsDisplayed()
        rule.onNodeWithText("修正后重新生成").assertIsDisplayed()
        rule.onNodeWithText("删除图片").assertIsDisplayed()
        rule.onNodeWithText("再次尝试").assertIsDisplayed()
    }

    @Test
    fun deletedOutputShowsPlaceholder() {
        val deleted = candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(false)))
        render(
            ResultUiState(
                loading = false,
                job = job(listOf(deleted)),
                selectedAssetId = deleted.outputs.first().assetId,
            ),
        )
        rule.onAllNodesWithText("素材已删除")[0].assertIsDisplayed()
    }

    @Test
    fun referenceConflictIsExplained() {
        val success = candidate(0, CandidateStateDomain.SUCCEEDED, outputs = listOf(output(true)))
        render(
            ResultUiState(
                loading = false,
                job = job(listOf(success)),
                conflict = ProblemModel("asset_referenced", "仍被引用", 409, false, referenceCount = 2),
            ),
        )
        rule.onNodeWithText("图片仍被 2 个引用使用，暂不能删除。").assertIsDisplayed()
    }
}
