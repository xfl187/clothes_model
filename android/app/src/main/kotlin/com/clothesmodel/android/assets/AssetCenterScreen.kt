package com.clothesmodel.android.assets

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.GarmentSource
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing

fun gridMinSizeDp(fontScale: Float): Dp = when {
    fontScale >= 1.8f -> 320.dp
    fontScale >= 1.3f -> 200.dp
    else -> 148.dp
}

@Composable
fun AssetCenterRoute(
    onCreate: () -> Unit,
    onOpenAsset: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: AssetCenterViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    AssetCenterScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onSegment = viewModel::selectSegment,
        onCategory = viewModel::setCategoryFilter,
        onImport = { uri, category, source -> viewModel.import(uri, category, source) },
        onRetryImport = viewModel::retryImport,
        onCancelImport = viewModel::cancelImport,
        onToggleFavorite = viewModel::toggleFavorite,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
        onOpenAsset = onOpenAsset,
        onCreate = onCreate,
    )
}

@Composable
fun AssetCenterScreen(
    state: AssetCenterUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onSegment: (AssetSegment) -> Unit,
    onCategory: (GarmentCategory?) -> Unit,
    onImport: (android.net.Uri, GarmentCategory, GarmentSource) -> Unit,
    onRetryImport: (String) -> Unit,
    onCancelImport: (String) -> Unit,
    onToggleFavorite: (AssetModel) -> Unit,
    onRefresh: () -> Unit,
    onLoadMore: () -> Unit,
    onOpenAsset: (String) -> Unit,
    onCreate: () -> Unit,
) {
    var pendingGarment by remember { mutableStateOf<android.net.Uri?>(null) }
    var garmentCategory by remember { mutableStateOf(GarmentCategory.UPPER_BODY) }
    var garmentSource by remember { mutableStateOf(GarmentSource.PHOTO) }
    val picker = rememberLauncherForActivityResult(PickVisualMedia()) { uri ->
        if (uri != null) {
            if (state.segment == AssetSegment.GARMENT) {
                pendingGarment = uri
            } else {
                onImport(uri, GarmentCategory.UPPER_BODY, GarmentSource.PHOTO)
            }
        }
    }
    val minColumn = gridMinSizeDp(LocalDensity.current.fontScale)

    AtelierScaffold(title = "素材", scrollable = false) {
        LazyVerticalGrid(
            columns = GridCells.Adaptive(minSize = minColumn),
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(0.dp),
            verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
            horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
        ) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
                    SectionHeading(
                        text = "素材库",
                        supporting = "人物与衣物只需导入一次，可重复使用。",
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                        AssetSegment.entries.forEach { segment ->
                            FilterChip(
                                selected = state.segment == segment,
                                onClick = { onSegment(segment) },
                                label = { Text(segment.label) },
                            )
                        }
                    }
                    if (state.segment == AssetSegment.GARMENT) {
                        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                            listOf(
                                null to "全部",
                                GarmentCategory.UPPER_BODY to "上装",
                                GarmentCategory.LOWER_BODY to "下装",
                                GarmentCategory.DRESS to "连衣裙",
                            ).forEach { (value, label) ->
                                FilterChip(
                                    selected = state.categoryFilter == value,
                                    onClick = { onCategory(value) },
                                    label = { Text(label) },
                                )
                            }
                        }
                    }
                    Button(
                        onClick = {
                            picker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly))
                        },
                        shape = AtelierShapes.PrimaryButton,
                        modifier = Modifier
                            .fillMaxWidth()
                            .sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
                    ) {
                        Text(if (state.segment == AssetSegment.PERSON) "导入人物图片" else "导入服装图片")
                    }
                    state.error?.let {
                        InlineProblem(
                            message = it.detail,
                            retryLabel = "重试",
                            onRetry = onRefresh,
                        )
                    }
                    if (state.imports.isNotEmpty()) {
                        SectionHeading(text = "正在导入")
                        state.imports.forEach { pending ->
                            ImportRow(
                                pending = pending,
                                onRetry = { onRetryImport(pending.id) },
                                onCancel = { onCancelImport(pending.id) },
                            )
                        }
                    }
                }
            }
            if (state.loading && state.assets.isEmpty()) {
                item(span = { GridItemSpan(maxLineSpan) }) { LoadingState(label = "正在加载素材") }
            } else {
                val filtered = state.assets.filter { asset ->
                    state.categoryFilter == null ||
                        asset.garmentCategory == state.categoryFilter
                }
                if (filtered.isEmpty() && state.imports.isEmpty()) {
                    item(span = { GridItemSpan(maxLineSpan) }) {
                        EmptyState(
                            title = "还没有素材",
                            message = "先导入一张图片，之后的任务都可以重复选择。",
                            actionLabel = "开始精准换装",
                            onAction = onCreate,
                        )
                    }
                }
                items(filtered, key = { it.id.toString() }) { asset ->
                    AssetTile(
                        asset = asset,
                        imageLoader = imageLoader,
                        onOpen = { onOpenAsset(asset.id.toString()) },
                        onToggleFavorite = { onToggleFavorite(asset) },
                    )
                }
            }
        }
    }

    pendingGarment?.let { uri ->
        AlertDialog(
            onDismissRequest = { pendingGarment = null },
            title = { Text("确认服装信息") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                    Text("服装类别", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                        listOf(
                            GarmentCategory.UPPER_BODY to "上装",
                            GarmentCategory.LOWER_BODY to "下装",
                            GarmentCategory.DRESS to "连衣裙",
                        ).forEach { (value, label) ->
                            FilterChip(
                                selected = garmentCategory == value,
                                onClick = { garmentCategory = value },
                                label = { Text(label) },
                            )
                        }
                    }
                    Text("图片来源", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                        listOf(
                            GarmentSource.PHOTO to "实拍",
                            GarmentSource.PRODUCT_IMAGE to "商品图",
                            GarmentSource.SCREENSHOT to "截图",
                            GarmentSource.EXPERIMENTAL to "实验性",
                        ).forEach { (value, label) ->
                            FilterChip(
                                selected = garmentSource == value,
                                onClick = { garmentSource = value },
                                label = { Text(label) },
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    pendingGarment = null
                    onImport(uri, garmentCategory, garmentSource)
                }) { Text("开始导入") }
            },
            dismissButton = {
                TextButton(onClick = { pendingGarment = null }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun AssetTile(
    asset: AssetModel,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onOpen: () -> Unit,
    onToggleFavorite: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
        Surface(
            onClick = onOpen,
            shape = AtelierShapes.Thumbnail,
            border = if (asset.favorite) {
                BorderStroke(2.dp, MaterialTheme.colorScheme.primary)
            } else {
                null
            },
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(3f / 4f)
                .semantics { role = Role.Button },
        ) {
            Box {
                AssetImage(
                    assetId = asset.id,
                    loader = imageLoader,
                    contentDescription = if (asset.favorite) "已收藏素材" else "素材",
                )
                if (asset.isDeletedContent) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(AtelierSpacing.sm),
                    ) {
                        Text("素材已删除", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = asset.kindLabel(),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(
                onClick = onToggleFavorite,
                modifier = Modifier.semantics {
                    contentDescription = if (asset.favorite) "取消收藏" else "收藏素材"
                },
            ) {
                Text(if (asset.favorite) "已收藏" else "收藏")
            }
        }
    }
}

private fun AssetModel.kindLabel(): String = when (kind) {
    "person" -> "人物"
    "garment" -> "衣物"
    "generated_output" -> "生成结果"
    "mask" -> "遮罩"
    else -> "素材"
}

@Composable
private fun ImportRow(
    pending: PendingImportUi,
    onRetry: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
        EntityCard(
            title = pending.displayName,
            subtitle = importStatusLabel(pending),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            if (pending.failed) {
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                ) { Text("重试上传") }
            }
            OutlinedButton(
                onClick = onCancel,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("取消导入") }
        }
    }
}

internal fun importStatusLabel(pending: PendingImportUi): String = when {
    pending.failed -> pending.error ?: "上传失败，可重试。"
    pending.state == "uploading" -> "正在上传 ${pending.uploadedBytes}/${pending.totalBytes}"
    pending.state == "completed" -> "上传完成"
    else -> "等待上传"
}
