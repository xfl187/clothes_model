package com.clothesmodel.android.outfits

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.ui.components.AtelierButton
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing
import com.clothesmodel.contract.model.LayerApplyState
import com.clothesmodel.contract.model.LayerRole
import com.clothesmodel.contract.model.OutfitRoute

private val ROLE_LABELS = mapOf(
    LayerRole.inner_top to "内搭",
    LayerRole.outerwear to "外套",
    LayerRole.lower_body to "下装",
    LayerRole.dress to "连衣裙",
)

@Composable
fun OutfitWorkbenchRoute(
    onBack: () -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: OutfitWorkbenchViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    OutfitWorkbenchScreen(
        state = state,
        onBack = onBack,
        onSelectRole = viewModel::selectRole,
        onSelectGarment = viewModel::selectGarment,
        onSelectProvider = viewModel::selectProvider,
        onSetCandidates = viewModel::setCandidates,
        onAddLayer = viewModel::addLayer,
        onSelectOutput = viewModel::selectOutput,
        onRemoveLayer = viewModel::removeLayer,
        onSwitchRoute = viewModel::switchRoute,
        onRefresh = viewModel::refresh,
    )
}

@Composable
fun OutfitWorkbenchScreen(
    state: WorkbenchUiState,
    onBack: () -> Unit,
    onSelectRole: (LayerRole) -> Unit,
    onSelectGarment: (java.util.UUID) -> Unit,
    onSelectProvider: (java.util.UUID) -> Unit,
    onSetCandidates: (Int) -> Unit,
    onAddLayer: () -> Unit,
    onSelectOutput: (java.util.UUID) -> Unit,
    onRemoveLayer: (java.util.UUID) -> Unit,
    onSwitchRoute: (OutfitRoute) -> Unit,
    onRefresh: () -> Unit,
) {
    AtelierScaffold(title = "穿搭工作台", onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            if (state.loading && state.session == null) {
                LoadingState(label = "正在读取穿搭会话")
                return@Column
            }
            if (state.error != null) {
                InlineProblem(
                    message = state.error.detail,
                    retryLabel = "重试",
                    onRetry = onRefresh,
                )
            }
            val session = state.session ?: return@Column

            SectionHeading(text = "当前确认结果")
            val confirmed = session.headRevision?.layers.orEmpty()
            if (confirmed.isEmpty()) {
                EmptyState(
                    title = "尚未确认任何层",
                    message = "添加第一件衣物并选择候选后，这里会显示确认结果。",
                )
            } else {
                confirmed.forEach { layer ->
                    LayerRow(
                        title = ROLE_LABELS[layer.role] ?: layer.role.value,
                        subtitle = "已应用 · 顺序 ${layer.order}",
                    )
                }
            }

            SectionHeading(text = "添加衣物层")
            Text("选择层级", style = MaterialTheme.typography.labelLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                session.layerTypes.forEach { definition ->
                    SelectableChip(
                        label = ROLE_LABELS[definition.key] ?: definition.key.value,
                        selected = state.selectedRole == definition.key,
                        onClick = { onSelectRole(definition.key) },
                    )
                }
            }
            Text("选择衣物", style = MaterialTheme.typography.labelLarge)
            if (state.garments.isEmpty()) {
                Text(
                    text = "素材库中没有衣物，请先导入。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                state.garments.forEach { garment ->
                    SelectableChip(
                        label = "衣物 ${garment.id.toString().take(8)}",
                        selected = state.selectedGarmentId == garment.id,
                        onClick = { onSelectGarment(garment.id) },
                    )
                }
            }
            Text("候选数：${state.candidates}", style = MaterialTheme.typography.labelLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                listOf(1, 2, 3, 4).forEach { count ->
                    SelectableChip(
                        label = count.toString(),
                        selected = state.candidates == count,
                        onClick = { onSetCandidates(count) },
                    )
                }
            }
            AtelierButton(
                onClick = onAddLayer,
                shape = AtelierShapes.PrimaryButton,
                enabled = !state.busy &&
                    state.selectedRole != null &&
                    state.selectedGarmentId != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("添加层并生成")
            }

            state.pendingJob?.let { job ->
                SectionHeading(text = "选择候选以提交版本")
                job.items.flatMap { it.outputs }.forEach { output ->
                    Surface(
                        shape = AtelierShapes.Secondary,
                        color = MaterialTheme.colorScheme.surface,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(enabled = !state.busy) { onSelectOutput(output.id) },
                    ) {
                        Text(
                            text = "候选 ${output.id.toString().take(8)}",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(AtelierSpacing.lg),
                        )
                    }
                }
                if (job.items.all { item -> item.outputs.isEmpty() }) {
                    Text(
                        text = "任务状态：${job.state.value}，完成后可选择候选。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            SectionHeading(text = "分支工作层")
            val branchId = session.mainBranchId
            val branch = session.branches.firstOrNull { it.id == branchId }
            branch?.layers.orEmpty().forEach { layer ->
                LayerRow(
                    title = ROLE_LABELS[layer.role] ?: layer.role.value,
                    subtitle = if (layer.state == LayerApplyState.pending_reapply) {
                        "待重新应用 · 顺序 ${layer.order}"
                    } else {
                        "已应用 · 顺序 ${layer.order}"
                    },
                    action = {
                        TextButton(
                            onClick = { onRemoveLayer(layer.id) },
                            enabled = !state.busy,
                        ) {
                            Text("移除")
                        }
                    },
                )
            }

            SectionHeading(text = "路线")
            Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                TextButton(
                    onClick = { onSwitchRoute(OutfitRoute.split) },
                    enabled = !state.busy,
                ) {
                    Text("切换到分体")
                }
                TextButton(
                    onClick = { onSwitchRoute(OutfitRoute.dress) },
                    enabled = !state.busy,
                ) {
                    Text("切换到连衣裙")
                }
            }
        }
    }
}

@Composable
private fun LayerRow(
    title: String,
    subtitle: String,
    action: (@Composable () -> Unit)? = null,
) {
    Surface(
        shape = AtelierShapes.Secondary,
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(AtelierSpacing.lg),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.xs)) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            action?.invoke()
        }
    }
}

@Composable
private fun SelectableChip(label: String, selected: Boolean, onClick: () -> Unit) {
    Surface(
        shape = AtelierShapes.Chip,
        color = if (selected) {
            MaterialTheme.colorScheme.primaryContainer
        } else {
            MaterialTheme.colorScheme.surfaceVariant
        },
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.padding(
                horizontal = AtelierSpacing.md,
                vertical = AtelierSpacing.sm,
            ),
        )
    }
}
