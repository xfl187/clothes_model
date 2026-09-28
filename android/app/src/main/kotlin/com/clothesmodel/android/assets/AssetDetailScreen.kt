package com.clothesmodel.android.assets

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.ConfirmationDialog
import com.clothesmodel.android.ui.components.DeletedContentPlaceholder
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun AssetDetailRoute(
    assetId: String,
    onBack: () -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: AssetDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    AssetDetailScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onBack = onBack,
        onToggleFavorite = viewModel::toggleFavorite,
        onDelete = viewModel::deleteContent,
        onDismissConflict = viewModel::dismissConflict,
        onRetry = viewModel::load,
        assetId = assetId,
    )
}

@Composable
fun AssetDetailScreen(
    state: AssetDetailUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onBack: () -> Unit,
    onToggleFavorite: () -> Unit,
    onDelete: () -> Unit,
    onDismissConflict: () -> Unit,
    onRetry: () -> Unit,
    assetId: String,
) {
    var confirmDelete by remember { mutableStateOf(false) }
    AtelierScaffold(title = "素材详情", onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            when {
                state.loading && state.asset == null -> LoadingState(label = "正在读取素材")
                state.error != null && state.asset == null -> InlineProblem(
                    message = state.error.detail,
                    retryLabel = "重试",
                    onRetry = onRetry,
                )

                state.asset != null -> {
                    val asset = state.asset
                    if (asset.contentAvailable) {
                        AssetImage(
                            assetId = asset.id,
                            loader = imageLoader,
                            contentDescription = "素材图片",
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
                    if (!asset.contentAvailable) {
                        Text("图片内容已删除，任务参数、错误和执行谱系仍然保留。")
                    }
                    if (asset.qualityWarnings.isNotEmpty()) {
                        InlineProblem(message = asset.qualityWarnings.joinToString("；"))
                    }
                    OutlinedButton(
                        onClick = onToggleFavorite,
                        modifier = Modifier
                            .fillMaxWidth()
                            .sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) {
                        Text(if (asset.favorite) "取消收藏" else "收藏素材")
                    }

                    SectionHeading(
                        text = "引用",
                        supporting = "活跃任务引用的素材不能删除内容。",
                    )
                    if (state.references.isEmpty()) {
                        Text("当前没有阻止删除的引用。")
                    } else {
                        state.references.forEach { reference ->
                            EntityCard(
                                title = reference.label ?: reference.sourceKind,
                                subtitle = "引用来源：${reference.sourceKind}",
                            )
                        }
                    }

                    if (asset.contentAvailable) {
                        Button(
                            onClick = { confirmDelete = true },
                            enabled = !state.busy,
                            modifier = Modifier
                                .fillMaxWidth()
                                .sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                        ) {
                            Text("删除图片")
                        }
                    }
                }
            }

            if (state.conflict != null) {
                InlineProblem(
                    message = "素材仍被 ${state.conflict.referenceCount ?: 0} 个活跃引用使用，暂不能删除。",
                    retryLabel = "了解",
                    onRetry = onDismissConflict,
                )
            }
        }
    }

    if (confirmDelete) {
        ConfirmationDialog(
            title = "删除图片？",
            message = "只会删除图片内容，任务参数、状态、错误和执行谱系会继续保留。删除后显示“素材已删除”占位。",
            confirmLabel = "删除图片",
            destructive = true,
            onConfirm = {
                confirmDelete = false
                onDelete()
            },
            onDismiss = { confirmDelete = false },
        )
    }

    if (assetId.isBlank()) {
        Text("素材 ID 无效。")
    }
}
