package com.clothesmodel.android.create

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.ui.components.AtelierScaffold
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
    onOpenAssets: () -> Unit,
    onAuthenticationExpired: () -> Unit = {},
    viewModel: CreateWizardViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.authenticationExpired) {
        if (state.authenticationExpired) onAuthenticationExpired()
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
        onCandidateCount = viewModel::setCandidateCount,
        onSubmit = { viewModel.submit(onCreated) },
        onOpenAssets = onOpenAssets,
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
    onOpenAssets: () -> Unit,
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
                    onOpenAssets = onOpenAssets,
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
                        onOpenAssets = onOpenAssets,
                    )
                }

                WizardStep.SETTINGS -> SettingsStep(
                    state = state,
                    onSelectProvider = onSelectProvider,
                    onCandidateCount = onCandidateCount,
                )
            }

            if (state.providerNote != null) {
                InlineProblem(message = state.providerNote)
            }

            state.createError?.let { InlineProblem(message = it.detail) }

            Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
                if (state.step != WizardStep.PERSON) {
                    OutlinedButton(
                        onClick = onPrevious,
                        modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
                    ) { Text("上一步") }
                }
                if (state.step == WizardStep.SETTINGS) {
                    Button(
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
                    Button(
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
    onOpenAssets: () -> Unit,
) {
    when {
        state.assetsLoading -> LoadingState(label = "正在读取素材")
        state.assetError != null -> InlineProblem(message = state.assetError.detail)
        state.assets.isEmpty() -> EmptyState(
            title = "还没有可用素材",
            message = "先导入一张图片，然后回到向导继续。",
            actionLabel = "去素材库导入",
            onAction = onOpenAssets,
        )

        else -> state.assets.forEach { asset ->
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
                ) {
                    com.clothesmodel.android.assets.AssetImage(
                        assetId = asset.id,
                        loader = imageLoader,
                        contentDescription = "素材缩略图",
                        modifier = Modifier
                            .sizeIn(
                                minWidth = AtelierSpacing.minTouchTarget,
                                minHeight = AtelierSpacing.minTouchTarget,
                            ),
                    )
                    Text(
                        text = if (asset.id == selectedId) {
                            "已选择 · ${asset.createdAt}"
                        } else {
                            "素材 ${asset.id.toString().take(8)}"
                        },
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
) {
    SectionHeading(text = "Provider", supporting = "提交后会锁定该 Provider 与版本。")
    if (state.providers.isEmpty()) {
        Text("当前没有可用 Provider，请联系管理员配置。")
    }
    val compatible = compatibleProviders(state.providers, state.garmentCategory)
    compatible.forEach { provider ->
        val selected = provider.id == state.providerId
        EntityCard(
            title = provider.displayName,
            subtitle = providerSubtitle(provider, selected),
            onClick = { onSelectProvider(provider) },
        )
    }

    SectionHeading(text = "候选数量", supporting = "数量越多，费用越高。")
    val limit = candidateLimit(state.selectedProvider)
    Row(horizontalArrangement = Arrangement.spacedBy(AtelierSpacing.md)) {
        OutlinedButton(
            onClick = { onCandidateCount(state.candidateCount - 1) },
            enabled = state.candidateCount > MIN_CANDIDATES,
            modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
        ) { Text("减少") }
        Text(
            text = "${state.candidateCount} 张",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(AtelierSpacing.md),
        )
        OutlinedButton(
            onClick = { onCandidateCount(state.candidateCount + 1) },
            enabled = state.candidateCount < limit,
            modifier = Modifier.sizeIn(minHeight = AtelierSpacing.minTouchTarget),
        ) { Text("增加") }
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
    return "$availability · 最多 ${provider.maxCandidates} 张$default$chosen"
}

private fun stepTitle(step: WizardStep): String = when (step) {
    WizardStep.PERSON -> "第 1 步：选择人物"
    WizardStep.GARMENT -> "第 2 步：选择衣物"
    WizardStep.SETTINGS -> "第 3 步：生成设置"
}
