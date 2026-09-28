package com.clothesmodel.android.results

import android.content.Intent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.assets.AssetImage
import com.clothesmodel.android.assets.gridMinSizeDp
import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.ConfirmationDialog
import com.clothesmodel.android.ui.components.DeletedContentPlaceholder
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.android.ui.theme.LocalAtelierTokens
import java.util.UUID

@Composable
fun ResultRoute(
    jobId: String,
    onBack: () -> Unit,
    onCompare: (String) -> Unit,
    onMask: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: ResultViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    LaunchedEffect(state.shareIntent) {
        state.shareIntent?.let {
            context.startActivity(Intent.createChooser(it, "分享试穿结果"))
            viewModel.consumeShareIntent()
        }
    }
    ResultScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onBack = onBack,
        onSelect = viewModel::select,
        onFavorite = viewModel::toggleFavorite,
        onDownload = viewModel::download,
        onShare = viewModel::share,
        onDelete = viewModel::deleteContent,
        onRetryCandidate = viewModel::retryCandidate,
        onCompare = onCompare,
        onMask = onMask,
        onDismissConflict = viewModel::dismissConflict,
        onDismissMessage = viewModel::dismissMessage,
    )
}

@Composable
fun ResultScreen(
    state: ResultUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onBack: () -> Unit,
    onSelect: (UUID) -> Unit,
    onFavorite: (UUID) -> Unit,
    onDownload: (UUID) -> Unit,
    onShare: (UUID) -> Unit,
    onDelete: (UUID) -> Unit,
    onRetryCandidate: (UUID) -> Unit,
    onCompare: (String) -> Unit,
    onMask: (String) -> Unit,
    onDismissConflict: () -> Unit,
    onDismissMessage: () -> Unit,
) {
    var confirmDelete by remember { mutableStateOf<UUID?>(null) }
    val minColumn = gridMinSizeDp(LocalDensity.current.fontScale)

    AtelierScaffold(title = "生成结果", onBack = onBack, scrollable = false) {
        when {
            state.loading && state.job == null -> LoadingState(label = "正在读取结果")
            state.error != null && state.job == null -> InlineProblem(
                message = state.error.detail,
                retryLabel = "重试",
                onRetry = onBack,
            )

            state.job != null -> {
                val job = state.job
                val items = galleryItems(job)
                val selected = items.firstOrNull { it.output.assetId == state.selectedAssetId }
                    ?: items.firstOrNull()
                LazyVerticalGrid(
                    columns = GridCells.Adaptive(minSize = minColumn),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(0.dp),
                    verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
                    horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
                ) {
                    item(span = { GridItemSpan(maxLineSpan) }) {
                        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
                            if (selected != null) {
                                SelectedResult(
                                    output = selected.output,
                                    imageLoader = imageLoader,
                                    busy = state.busy,
                                    onFavorite = { onFavorite(selected.output.assetId) },
                                    onDownload = { onDownload(selected.output.assetId) },
                                    onShare = { onShare(selected.output.assetId) },
                                    onDelete = { confirmDelete = selected.output.assetId },
                                    onCompare = { onCompare(selected.output.assetId.toString()) },
                                    onMask = { onMask(selected.output.assetId.toString()) },
                                )
                            }
                            if (state.message != null) {
                                InlineProblem(message = state.message, retryLabel = "了解", onRetry = onDismissMessage)
                            }
                            if (state.conflict != null) {
                                InlineProblem(
                                    message = "图片仍被 ${state.conflict.referenceCount ?: 0} 个引用使用，暂不能删除。",
                                    retryLabel = "了解",
                                    onRetry = onDismissConflict,
                                )
                            }
                            if (items.isEmpty()) {
                                EmptyState(
                                    title = "暂无成功结果",
                                    message = "全部候选失败或取消，可在下方查看并重试。",
                                )
                            } else {
                                SectionHeading(text = "全部候选结果")
                            }
                        }
                    }
                    items(items, key = { it.output.assetId.toString() }) { item ->
                        Surface(
                            onClick = { onSelect(item.output.assetId) },
                            shape = AtelierShapes.Thumbnail,
                            border = if (item.output.assetId == state.selectedAssetId) {
                                BorderStroke(2.dp, MaterialTheme.colorScheme.primary)
                            } else {
                                null
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio(3f / 4f),
                        ) {
                            if (item.output.contentAvailable) {
                                AssetImage(
                                    assetId = item.output.assetId,
                                    loader = imageLoader,
                                    contentDescription = "候选 ${item.candidateIndex + 1} 结果",
                                )
                            } else {
                                DeletedContentPlaceholder(label = "素材已删除")
                            }
                        }
                    }
                    val traceable = traceableCandidates(job)
                    if (traceable.isNotEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            SectionHeading(text = "失败或取消的候选")
                        }
                    }
                    items(traceable, key = { it.id.toString() }) { candidate ->
                        TraceableRow(candidate = candidate, onRetry = { onRetryCandidate(candidate.id) })
                    }
                }
            }
        }
    }

    confirmDelete?.let { assetId ->
        ConfirmationDialog(
            title = "删除图片？",
            message = "只删除图片内容，任务参数、错误与谱系继续保留，并显示“素材已删除”占位。",
            confirmLabel = "删除图片",
            destructive = true,
            onConfirm = {
                confirmDelete = null
                onDelete(assetId)
            },
            onDismiss = { confirmDelete = null },
        )
    }
}

@Composable
private fun SelectedResult(
    output: com.clothesmodel.android.data.JobOutputModel,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    busy: Boolean,
    onFavorite: () -> Unit,
    onDownload: () -> Unit,
    onShare: () -> Unit,
    onDelete: () -> Unit,
    onCompare: () -> Unit,
    onMask: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
        if (output.contentAvailable) {
            AssetImage(
                assetId = output.assetId,
                loader = imageLoader,
                contentDescription = "当前选择的结果",
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(3f / 4f),
            )
        } else {
            DeletedContentPlaceholder(
                label = "素材已删除",
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(3f / 4f),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            OutlinedButton(
                onClick = onFavorite,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text(if (output.favorite) "取消收藏" else "收藏") }
            OutlinedButton(
                onClick = onCompare,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("原图对比") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            OutlinedButton(
                onClick = onDownload,
                enabled = output.contentAvailable && !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("下载") }
            OutlinedButton(
                onClick = onShare,
                enabled = output.contentAvailable && !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("分享") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            Button(
                onClick = onMask,
                enabled = output.contentAvailable,
                shape = AtelierShapes.PrimaryButton,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("修正后重新生成") }
            OutlinedButton(
                onClick = onDelete,
                enabled = output.contentAvailable && !busy,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("删除图片") }
        }
    }
}

@Composable
private fun TraceableRow(candidate: CandidateModel, onRetry: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
        EntityCard(
            title = "候选 ${candidate.candidateIndex + 1}",
            subtitle = "第 ${candidate.attempt} 次尝试 · ${candidate.errorDetail ?: "未产生图片"}",
            status = null,
            statusLabel = null,
        )
        candidate.errorDetail?.let {
            Text(it, color = LocalAtelierTokens.current.error, style = MaterialTheme.typography.bodyMedium)
        }
        OutlinedButton(
            onClick = onRetry,
            modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
        ) { Text("再次尝试") }
    }
}
