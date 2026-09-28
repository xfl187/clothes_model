package com.clothesmodel.android.mask

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.assets.AssetImage
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.ConfirmationDialog
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.android.ui.theme.LocalAtelierTokens

@Composable
fun MaskEditorRoute(
    jobId: String,
    candidateId: String,
    onBack: () -> Unit,
    onCreated: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: MaskViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    var showDiscard by remember { mutableStateOf(false) }
    BackHandler(enabled = state.hasUnsavedEdits) { showDiscard = true }
    MaskEditorScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onBack = {
            if (state.hasUnsavedEdits) showDiscard = true else onBack()
        },
        onTool = viewModel::setTool,
        onRadius = viewModel::setRadius,
        onTogglePreview = viewModel::togglePreview,
        onStart = viewModel::startStroke,
        onExtend = viewModel::extendStroke,
        onStrokeEnd = viewModel::persistDraft,
        onUndo = viewModel::undo,
        onClear = viewModel::clear,
        onSelectProvider = viewModel::selectProvider,
        onSubmit = { viewModel.submit(onCreated) },
    )
    if (showDiscard) {
        ConfirmationDialog(
            title = "放弃遮罩编辑？",
            message = "当前未提交的遮罩编辑会被丢弃，原任务与结果不受影响。",
            confirmLabel = "放弃编辑",
            destructive = true,
            onConfirm = {
                showDiscard = false
                viewModel.discard()
                onBack()
            },
            onDismiss = { showDiscard = false },
        )
    }
}

@Composable
fun MaskEditorScreen(
    state: MaskEditorUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onBack: () -> Unit,
    onTool: (MaskTool) -> Unit,
    onRadius: (Float) -> Unit,
    onTogglePreview: () -> Unit,
    onStart: (MaskPoint) -> Unit,
    onExtend: (MaskPoint) -> Unit,
    onStrokeEnd: () -> Unit,
    onUndo: () -> Unit,
    onClear: () -> Unit,
    onSelectProvider: (java.util.UUID) -> Unit,
    onSubmit: () -> Unit,
) {
    AtelierScaffold(title = "遮罩修正", onBack = onBack) {
        when {
            state.loading -> LoadingState(label = "正在准备遮罩编辑")
            state.error != null -> InlineProblem(message = state.error.detail, retryLabel = "重试", onRetry = onBack)
            else -> Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
                val maskColor = LocalAtelierTokens.current.plum.copy(alpha = 0.45f)
                val aspect = if (state.sourceHeight > 0) {
                    state.sourceWidth.toFloat() / state.sourceHeight.toFloat()
                } else {
                    0.75f
                }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(aspect)
                        .graphicsLayer(compositingStrategy = CompositingStrategy.Offscreen),
                ) {
                    state.sourceAssetId?.let { source ->
                        AssetImage(
                            assetId = source,
                            loader = imageLoader,
                            contentDescription = "待修正的源图",
                            contentScale = androidx.compose.ui.layout.ContentScale.Fit,
                        )
                    }
                    Canvas(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(aspect)
                            .pointerInput(state.activeTool, state.radius) {
                                detectDragGestures(
                                    onDragStart = { offset -> onStart(offset.toMaskPoint(size.width, size.height)) },
                                    onDrag = { change, _ ->
                                        change.consume()
                                        onExtend(change.position.toMaskPoint(size.width, size.height))
                                    },
                                    onDragEnd = { onStrokeEnd() },
                                )
                            }
                            .pointerInput(state.activeTool, state.radius) {
                                detectTapGestures { offset ->
                                    onStart(offset.toMaskPoint(size.width, size.height))
                                    onStrokeEnd()
                                }
                            },
                    ) {
                        state.document.strokes.forEach { stroke ->
                            val widthPx = brushRadiusPx(
                                stroke.radius,
                                size.width.toInt(),
                                size.height.toInt(),
                            ) * 2f
                            val erase = stroke.tool == MaskTool.ERASE
                            val color = if (state.showPreview) {
                                maskColor
                            } else {
                                androidx.compose.ui.graphics.Color.Transparent
                            }
                            if (stroke.points.size == 1) {
                                val point = stroke.points.first()
                                drawCircle(
                                    color = color,
                                    radius = widthPx / 2f,
                                    center = Offset(point.x * size.width, point.y * size.height),
                                    blendMode = if (erase) BlendMode.Clear else BlendMode.SrcOver,
                                )
                            } else {
                                val path = Path()
                                stroke.points.forEachIndexed { index, point ->
                                    val x = point.x * size.width
                                    val y = point.y * size.height
                                    if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                                }
                                drawPath(
                                    path = path,
                                    color = color,
                                    style = Stroke(
                                        width = widthPx,
                                        cap = StrokeCap.Round,
                                        join = StrokeJoin.Round,
                                    ),
                                    blendMode = if (erase) BlendMode.Clear else BlendMode.SrcOver,
                                )
                            }
                        }
                    }
                }

                Text("当前工具：${toolLabel(state.activeTool)} · 粗细 ${(state.radius * 100).toInt()}")
                Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                    FilterChip(
                        selected = state.activeTool == MaskTool.DRAW,
                        onClick = { onTool(MaskTool.DRAW) },
                        label = { Text("画笔") },
                    )
                    FilterChip(
                        selected = state.activeTool == MaskTool.ERASE,
                        onClick = { onTool(MaskTool.ERASE) },
                        label = { Text("擦除") },
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                    brushSizeOptions.forEach { option ->
                        FilterChip(
                            selected = state.radius == option,
                            onClick = { onRadius(option) },
                            label = { Text("${(option * 100).toInt()}") },
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                    OutlinedButton(
                        onClick = onUndo,
                        enabled = state.document.strokes.isNotEmpty(),
                        modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) { Text("撤销") }
                    OutlinedButton(
                        onClick = onClear,
                        enabled = state.document.strokes.isNotEmpty(),
                        modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) { Text("清空") }
                    OutlinedButton(
                        onClick = onTogglePreview,
                        modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) { Text(if (state.showPreview) "隐藏遮罩" else "显示遮罩") }
                }

                if (state.providerNote != null) {
                    InlineProblem(message = state.providerNote)
                    SectionHeading(text = "选择兼容 Provider")
                    if (state.compatibleManualMaskProviders.isEmpty()) {
                        Text("当前没有支持手动遮罩的 Provider，无法执行遮罩修正。")
                    }
                    state.compatibleManualMaskProviders.forEach { provider ->
                        val selected = provider.id == state.selectedProviderId
                        EntityCard(
                            title = provider.displayName,
                            subtitle = if (selected) "已选择" else "支持手动遮罩",
                            onClick = { onSelectProvider(provider.id) },
                        )
                    }
                }
                if (state.providerNote == null) {
                    Text("将复用原 Provider：${state.job?.providerLabel ?: ""}")
                }

                state.submitError?.let { InlineProblem(message = it.detail) }

                Button(
                    onClick = onSubmit,
                    enabled = state.canSubmit,
                    shape = AtelierShapes.PrimaryButton,
                    modifier = Modifier
                        .fillMaxWidth()
                        .sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
                ) {
                    Text(if (state.submitting) "正在提交修正任务" else "修正后重新生成")
                }
                Text("修正会创建与原任务关联的新主任务，原任务与结果保持不变。")
            }
        }
    }
}

private fun toolLabel(tool: MaskTool): String = when (tool) {
    MaskTool.DRAW -> "画笔"
    MaskTool.ERASE -> "擦除"
}

private fun Offset.toMaskPoint(width: Int, height: Int): MaskPoint = MaskPoint(
    x = if (width == 0) 0f else (x / width).coerceIn(0f, 1f),
    y = if (height == 0) 0f else (y / height).coerceIn(0f, 1f),
)
