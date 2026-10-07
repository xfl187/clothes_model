package com.clothesmodel.android.create

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.ui.components.AtelierScaffold
import com.clothesmodel.android.ui.components.AtelierButton
import com.clothesmodel.android.ui.components.AtelierOutlinedButton
import com.clothesmodel.android.ui.components.EmptyState
import com.clothesmodel.android.ui.components.EntityCard
import com.clothesmodel.android.ui.components.InlineProblem
import com.clothesmodel.android.ui.components.LoadingState
import com.clothesmodel.android.ui.components.SectionHeading
import com.clothesmodel.android.ui.theme.AtelierShapes
import com.clothesmodel.android.ui.theme.AtelierSpacing

@Composable
fun CreateWizardRoute(
    onBack: () -> Unit,
    onCreated: (String) -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: CreateWizardViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
    }
    val picker = rememberLauncherForActivityResult(PickVisualMedia()) { uri ->
        uri?.let(viewModel::import)
    }
    CreateWizardScreen(
        state = state,
        imageLoader = viewModel.imageLoader,
        onBack = onBack,
        onNext = viewModel::next,
        onPrevious = viewModel::back,
        onSelectPerson = viewModel::selectPerson,
        onSelectGarment = viewModel::selectGarment,
        onCategory = viewModel::setGarmentCategory,
        onSelectProvider = viewModel::selectProvider,
        onRetryProviders = viewModel::retryProviders,
        onCandidateCount = viewModel::setCandidateCount,
        onSubmit = { viewModel.submit(onCreated) },
        onImport = { picker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) },
        onRetryImport = viewModel::retryImport,
        onCancelImport = viewModel::cancelImport,
    )
}

@Composable
fun CreateWizardScreen(
    state: CreateWizardUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onPrevious: () -> Unit,
    onSelectPerson: (AssetModel) -> Unit,
    onSelectGarment: (AssetModel) -> Unit,
    onCategory: (GarmentCategory) -> Unit,
    onSelectProvider: (ProviderModel) -> Unit,
    onCandidateCount: (Int) -> Unit,
    onSubmit: () -> Unit,
    onImport: () -> Unit,
    onRetryImport: (String) -> Unit,
    onCancelImport: (String) -> Unit,
    onRetryProviders: () -> Unit = {},
) {
    AtelierScaffold(title = "精准换装", onBack = onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(AtelierSpacing.lg)) {
            Text(
                text = stepTitle(state.step),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.semantics { heading() },
            )
            when (state.step) {
                WizardStep.PERSON -> AssetStep(
                    state = state,
                    imageLoader = imageLoader,
                    selectedId = state.personAsset?.id,
                    onSelect = onSelectPerson,
                    onImport = onImport,
                    onRetryImport = onRetryImport,
                    onCancelImport = onCancelImport,
                    importLabel = "从相册导入人物",
                )

                WizardStep.GARMENT -> {
                    SectionHeading(text = "衣物类别")
                    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
                        listOf(
                            GarmentCategory.UPPER_BODY to "上装",
                            GarmentCategory.LOWER_BODY to "下装",
                            GarmentCategory.DRESS to "连衣裙",
                        ).forEach { (value, label) ->
                            FilterChip(
                                selected = state.garmentCategory == value,
                                onClick = { onCategory(value) },
                                label = { Text(label) },
                            )
                        }
                    }
                    AssetStep(
                        state = state,
                        imageLoader = imageLoader,
                        selectedId = state.garmentAsset?.id,
                        onSelect = onSelectGarment,
                        onImport = onImport,
                        onRetryImport = onRetryImport,
                        onCancelImport = onCancelImport,
                        importLabel = "从相册导入衣物",
                    )
                }

                WizardStep.SETTINGS -> SettingsStep(
                    state = state,
                    onSelectProvider = onSelectProvider,
                    onCandidateCount = onCandidateCount,
                    onRetryProviders = onRetryProviders,
                )
            }

            if (state.providerNote != null) {
                InlineProblem(message = state.providerNote)
            }

            state.createError?.let { InlineProblem(message = it.detail) }

            Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
                if (state.step != WizardStep.PERSON) {
                    AtelierOutlinedButton(
                        onClick = onPrevious,
                        modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) { Text("上一步") }
                }
                if (state.step == WizardStep.SETTINGS) {
                    AtelierButton(
                        onClick = onSubmit,
                        enabled = state.canAdvance && !state.submitting,
                        shape = AtelierShapes.PrimaryButton,
                        modifier = Modifier
                            .fillMaxWidth()
                            .sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
                    ) {
                        Text(if (state.submitting) "正在创建任务" else "生成试穿结果")
                    }
                } else {
                    AtelierButton(
                        onClick = onNext,
                        enabled = state.canAdvance,
                        shape = AtelierShapes.PrimaryButton,
                        modifier = Modifier
                            .fillMaxWidth()
                            .sizeIn(minHeight = AtelierSpacing.primaryButtonMinHeight),
                    ) { Text("下一步") }
                }
            }
        }
    }
}

@Composable
private fun AssetStep(
    state: CreateWizardUiState,
    imageLoader: com.clothesmodel.android.data.AuthenticatedImageLoader,
    selectedId: java.util.UUID?,
    onSelect: (AssetModel) -> Unit,
    onImport: () -> Unit,
    onRetryImport: (String) -> Unit,
    onCancelImport: (String) -> Unit,
    importLabel: String,
) {
    AtelierOutlinedButton(
        onClick = onImport,
        modifier = Modifier
            .fillMaxWidth()
            .sizeIn(minHeight = AtelierSpacing.minTouchTarget),
    ) {
        Text(importLabel)
    }
    state.currentImport?.let { pending ->
        Text(
            text = if (pending.failed) {
                pending.error ?: "上传失败，可重试或取消。"
            } else {
                "图片已保存在本机，正在后台上传。"
            },
            color = if (pending.failed) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
        )
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.sm)) {
            if (pending.failed) {
                AtelierOutlinedButton(onClick = { onRetryImport(pending.id) }) { Text("重试") }
            }
            AtelierOutlinedButton(onClick = { onCancelImport(pending.id) }) { Text("取消上传") }
        }
    }
    when {
        state.assetsLoading -> LoadingState(label = "正在读取素材")
        state.assetError != null -> InlineProblem(message = state.assetError.detail)
        state.assets.isEmpty() -> EmptyState(
            title = "还没有可用素材",
            message = "可直接从相册导入，上传完成后会自动选中。",
        )

        state.visibleAssets.isEmpty() -> EmptyState(
            title = "当前分类还没有衣物",
            message = "切换分类，或直接从相册导入当前类别的衣物。",
        )

        else -> state.visibleAssets.forEach { asset ->
            Surface(
                onClick = { onSelect(asset) },
                shape = AtelierShapes.Thumbnail,
                border = if (asset.id == selectedId) {
                    BorderStroke(2.dp, MaterialTheme.colorScheme.primary)
                } else {
                    null
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(AtelierSpacing.sm),
                    horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    com.clothesmodel.android.assets.AssetImage(
                        assetId = asset.id,
                        loader = imageLoader,
                        localPath = asset.localPath,
                        contentDescription = "素材缩略图",
                        modifier = Modifier.size(96.dp),
                    )
                    Text(
                        text = if (asset.id == selectedId) {
                            "已选择 · ${asset.createdAt}"
                        } else {
                            "素材 ${asset.id.toString().take(8)}"
                        },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
    if (selectedId != null) {
        Text("当前已选择素材 ${selectedId.toString().take(8)}")
    }
}

@Composable
private fun SettingsStep(
    state: CreateWizardUiState,
    onSelectProvider: (ProviderModel) -> Unit,
    onCandidateCount: (Int) -> Unit,
    onRetryProviders: () -> Unit,
) {
    SectionHeading(text = "Provider", supporting = "提交后会锁定该 Provider 与版本。")
    val compatible = compatibleProviders(state.providers, state.garmentCategory)
    val unavailable = state.providers.filterNot { it in compatible }
    when {
        state.loading && state.providers.isEmpty() -> LoadingState(label = "正在检查 Provider")
        state.providerError != null -> InlineProblem(
            message = "无法读取 Provider：${state.providerError.detail}",
            retryLabel = "重新检查",
            onRetry = onRetryProviders,
        )
        compatible.isEmpty() -> InlineProblem(
            message = generationBlockingReason(state)
                ?: "当前没有可用 Provider，请管理员检查配置。",
            retryLabel = "重新检查",
            onRetry = onRetryProviders,
        )
    }
    compatible.forEach { provider ->
        val selected = provider.id == state.providerId
        EntityCard(
            title = provider.displayName,
            subtitle = providerSubtitle(provider, selected),
            onClick = { onSelectProvider(provider) },
        )
    }
    if (unavailable.isNotEmpty()) {
        SectionHeading(
            text = "暂不可用",
            supporting = "以下 Provider 不能用于本次生成。",
        )
        unavailable.forEach { provider ->
            EntityCard(
                title = provider.displayName,
                subtitle = unavailableProviderSubtitle(provider, state.garmentCategory),
            )
        }
    }

    SectionHeading(text = "候选数量", supporting = "数量越多，费用越高。")
    val limit = candidateLimit(state.selectedProvider)
    val fixedMessage = candidateCountFixedMessage(state.selectedProvider)
    if (fixedMessage != null) {
        Text(
            text = fixedMessage,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    } else {
        Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
            AtelierOutlinedButton(
                onClick = { onCandidateCount(state.candidateCount - 1) },
                enabled = state.candidateCount > MIN_CANDIDATES,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("减少") }
            Text(
                text = "${state.candidateCount} 张",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(AtelierSpacing.md),
            )
            AtelierOutlinedButton(
                onClick = { onCandidateCount(state.candidateCount + 1) },
                enabled = state.candidateCount < limit,
                modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
            ) { Text("增加") }
        }
    }

    val provider = state.selectedProvider
    if (provider != null && provider.availability == ProviderAvailabilityDomain.TEMPORARILY_OFFLINE) {
        InlineProblem(message = "该 Provider 暂时离线，任务会先进入等待状态，恢复后自动继续。")
    }
}

private fun providerSubtitle(provider: ProviderModel, selected: Boolean): String {
    val availability = when (provider.availability) {
        ProviderAvailabilityDomain.AVAILABLE -> "可用"
        ProviderAvailabilityDomain.TEMPORARILY_OFFLINE -> "暂时离线，可先创建"
        ProviderAvailabilityDomain.UNAVAILABLE_CONFIGURATION -> "配置不可用"
        ProviderAvailabilityDomain.DISABLED -> "已禁用"
        ProviderAvailabilityDomain.UNKNOWN -> "状态未知"
    }
    val default = if (provider.isDefault) " · 默认" else ""
    val chosen = if (selected) " · 已选择" else ""
    val reason = provider.unavailableReason?.let { " · $it" }.orEmpty()
    return "$availability · 最多 ${provider.maxCandidates} 张$default$chosen$reason"
}

private fun unavailableProviderSubtitle(
    provider: ProviderModel,
    category: GarmentCategory,
): String = when {
    !categoryCompatible(provider, category) -> "不支持当前衣物类别"
    provider.unavailableReason != null -> provider.unavailableReason
    else -> providerSubtitle(provider, selected = false)
}

private fun stepTitle(step: WizardStep): String = when (step) {
    WizardStep.PERSON -> "第 1 步：选择人物"
    WizardStep.GARMENT -> "第 2 步：选择衣物"
    WizardStep.SETTINGS -> "第 3 步：生成设置"
}
