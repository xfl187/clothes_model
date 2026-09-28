package com.clothesmodel.android.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.assets.AssetImage
import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.DeletedContentPlaceholder
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.components.StatusMarker
import com.clothesmodel.android.ui.components.blockLabel
import com.clothesmodel.android.ui.components.statusLabel
import com.clothesmodel.android.ui.components.toAtelierStatus
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import java.util.UUID

@Composable
fun JobDetailRoute(
    jobId: String,
    onBack: () -> Unit,
    onOpenResults: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: JobDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    LifecycleResumeEffect(Unit) {
        viewModel.onResumed()
        onPauseOrDispose { viewModel.onPaused() }
    }
    JobDetailScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        jobId = jobId,
        onBack = onBack,
        onOpenResults = { onOpenResults(jobId) },
        onCancelJob = viewModel::cancelJob,
        onCancelCandidate = viewModel::cancelCandidate,
        onRetryCandidate = viewModel::requestRetry,
        onRequeryCandidate = viewModel::requeryCandidate,
        onFinishFailed = viewModel::finishFailed,
        onConfirmRetry = viewModel::confirmRetry,
        onDismissRetry = viewModel::dismissRetry,
        onDismissCommandError = viewModel::dismissCommandError,
    )
}

@Composable
fun JobDetailScreen(
    state: JobDetailUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    jobId: String,
    onBack: () -> Unit,
    onOpenResults: () -> Unit,
    onCancelJob: () -> Unit,
    onCancelCandidate: (UUID) -> Unit,
    onRetryCandidate: (UUID) -> Unit,
    onRequeryCandidate: (UUID) -> Unit,
    onFinishFailed: (UUID, String) -> Unit,
    onConfirmRetry: (UUID) -> Unit,
    onDismissRetry: () -> Unit,
    onDismissCommandError: () -> Unit,
) {
    var finishTarget by remember { mutableStateOf<UUID?>(null) }
    AtelierScaffold(title = "任务详情", onBack = onBack) {
        when {
            state.loading && state.job == null -> LoadingState(label = "正在读取任务")
            state.error != null && state.job == null -> InlineProblem(
                message = state.error.detail,
                retryLabel = "重试",
                onRetry = onBack,
            )

            state.job != null -> {
                val job = state.job
                AggregatePanel(
                    job = job,
                    busy = state.busy.contains("cancel-job"),
                    stale = state.stale,
                    onCancelJob = onCancelJob,
                    onOpenResults = onOpenResults,
                )
                if (state.commandError != null) {
                    InlineProblem(
                        message = state.commandError.detail,
                        retryLabel = "了解",
                        onRetry = onDismissCommandError,
                    )
                }
                LockedConfiguration(job)
                SectionHeading(
                    text = "候选",
                    supporting = "成功结果优先保留，失败或不确定的候选可单独处理。",
                )
                job.candidates.forEach { candidate ->
                    CandidateCard(
                        candidate = candidate,
                        imageLoader = imageLoader,
                        busy = state.busy.any { it.endsWith(candidate.id.toString()) },
                        onCancel = { onCancelCandidate(candidate.id) },
                        onRetry = { onRetryCandidate(candidate.id) },
                        onRequery = { onRequeryCandidate(candidate.id) },
                        onFinish = { finishTarget = candidate.id },
                    )
                }
            }
        }
    }

    state.retrySelection?.let { selection ->
        RetryProviderDialog(
            providers = state.providers,
            originalProviderId = state.job?.lockedProviderId,
            onConfirm = onConfirmRetry,
            onDismiss = onDismissRetry,
        )
    }

    finishTarget?.let { itemId ->
        FinishReasonDialog(
            onConfirm = { reason ->
                finishTarget = null
                onFinishFailed(itemId, reason)
            },
            onDismiss = { finishTarget = null },
        )
    }

    if (jobId.isBlank()) {
        Text("任务 ID 无效。")
    }
}

@Composable
private fun AggregatePanel(
    job: JobModel,
    busy: Boolean,
    stale: Boolean,
    onCancelJob: () -> Unit,
    onOpenResults: () -> Unit,
) {
    val succeeded = succeededCandidates(job.candidates)
    val failed = failedCandidates(job.candidates)
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
        Text(
            text = job.providerLabel,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.semantics { heading() },
        )
        StatusMarker(status = job.state.toAtelierStatus(), label = job.state.statusLabel())
        Text("已运行 ${formatElapsed(job.createdAt, job.updatedAt)} · 候选 ${job.candidates.size} 个")
        Text("成功 $succeeded · 失败 $failed")
        job.blockReason?.let { Text(it.blockLabel(), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        job.blockedDetail?.let { Text(it) }
        if (stale) {
            Text("当前显示的是上一次同步结果，网络恢复后会自动刷新。")
        }
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
            if (job.candidates.any { candidate -> candidate.outputs.any { it.contentAvailable } }) {
                Button(
                    onClick = onOpenResults,
                    shape = AtelierShapes.PrimaryButton,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text("查看结果") }
            }
            if (canCancelJob(job.state)) {
                OutlinedButton(
                    onClick = onCancelJob,
                    enabled = !busy,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text(if (busy) "正在取消" else "取消任务") }
            }
        }
    }
}

@Composable
private fun LockedConfiguration(job: JobModel) {
    var expanded by remember { mutableStateOf(false) }
    SectionHeading(text = "锁定配置")
    EntityCard(
        title = job.providerLabel,
        subtitle = if (expanded) {
            buildString {
                append("候选数量：${job.candidateCount}")
                job.workflowLabel?.let { append(" · Workflow：$it") }
                job.maskAssetId?.let { append(" · 含遮罩修正") }
                job.relatedJobId?.let { append(" · 关联任务 ${it.toString().take(8)}") }
            }
        } else {
            "候选数量 ${job.candidateCount} · 展开查看 Workflow 与谱系"
        },
        onClick = { expanded = !expanded },
    )
}

@Composable
private fun CandidateCard(
    candidate: CandidateModel,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    busy: Boolean,
    onCancel: () -> Unit,
    onRetry: () -> Unit,
    onRequery: () -> Unit,
    onFinish: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
        EntityCard(
            title = "候选 ${candidate.candidateIndex + 1}",
            subtitle = "第 ${candidate.attempt} 次尝试 · ${candidateStateLabel(candidate.state)}" +
                candidate.blockReason?.let { " · ${it.blockLabel()}" }.orEmpty(),
        )
        candidate.outputs.forEach { output ->
            if (output.contentAvailable) {
                AssetImage(
                    assetId = output.assetId,
                    loader = imageLoader,
                    contentDescription = "候选 ${candidate.candidateIndex + 1} 结果",
                    modifier = Modifier
                        .fillMaxWidth()
                        .size(160.dp),
                )
            } else {
                DeletedContentPlaceholder(
                    label = "素材已删除",
                    modifier = Modifier
                        .fillMaxWidth()
                        .size(160.dp),
                )
            }
        }
        candidate.errorDetail?.let {
            InlineProblem(message = it)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            if (canCancelCandidate(candidate.state)) {
                OutlinedButton(
                    onClick = onCancel,
                    enabled = !busy,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text("取消候选") }
            }
            if (canRetryCandidate(candidate.state)) {
                OutlinedButton(
                    onClick = onRetry,
                    enabled = !busy,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text("再次尝试") }
            }
            if (needsAttentionActions(candidate.state)) {
                NeedsAttentionActions(
                    busy = busy,
                    onRequery = onRequery,
                    onRetry = onRetry,
                    onFinish = onFinish,
                )
            }
        }
        Lineage(candidate)
    }
}

@Composable
private fun NeedsAttentionActions(
    busy: Boolean,
    onRequery: () -> Unit,
    onRetry: () -> Unit,
    onFinish: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
        Text("自动推进已停止。请选择：重新查询、明确重试或结束失败。")
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            OutlinedButton(
                onClick = onRequery,
                enabled = !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("重新查询") }
            OutlinedButton(
                onClick = onRetry,
                enabled = !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("明确重试") }
            OutlinedButton(
                onClick = onFinish,
                enabled = !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("结束失败") }
        }
    }
}

@Composable
private fun Lineage(candidate: CandidateModel) {
    var expanded by remember { mutableStateOf(false) }
    TextButton(onClick = { expanded = !expanded }) {
        Text(if (expanded) "收起执行谱系" else "展开执行谱系")
    }
    if (expanded) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
            Text("尝试次数：${candidate.attempt}")
            candidate.retryOfJobItemId?.let { Text("重试来源：${it.toString().take(8)}") }
            candidate.supersededByJobItemId?.let { Text("已被新尝试替代：${it.toString().take(8)}") }
            candidate.externalExecutionId?.let { Text("外部执行标识：$it") }
            candidate.errorCode?.let { Text("错误代码：$it") }
        }
    }
}

@Composable
private fun RetryProviderDialog(
    providers: List<ProviderModel>,
    originalProviderId: UUID?,
    onConfirm: (UUID) -> Unit,
    onDismiss: () -> Unit,
) {
    val compatible = providers.filter { it.selectable }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("选择兼容 Provider") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                Text("原 Provider 当前不可复用。请选择一个兼容的 Provider 后重试。")
                compatible.forEach { provider ->
                    val original = provider.id == originalProviderId
                    TextButton(onClick = { onConfirm(provider.id) }) {
                        Text(
                            if (original) "原 Provider：${provider.displayName}" else provider.displayName,
                        )
                    }
                }
                if (compatible.isEmpty()) {
                    Text("当前没有兼容的 Provider，暂时无法执行该重试。")
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun FinishReasonDialog(
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var reason by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("结束为失败") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                Text("请填写人工确认的失败原因，任务参数与谱系会继续保留。")
                androidx.compose.material3.OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("失败原因") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(reason) },
                enabled = reason.isNotBlank(),
            ) { Text("确认结束") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
