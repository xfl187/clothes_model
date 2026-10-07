package com.clothesmodel.android.create

import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel

const val MIN_CANDIDATES = 1
const val MAX_CANDIDATES = 4

fun selectableProviders(providers: List<ProviderModel>): List<ProviderModel> =
    providers.filter {
        it.availability == ProviderAvailabilityDomain.AVAILABLE ||
            it.availability == ProviderAvailabilityDomain.TEMPORARILY_OFFLINE
    }

fun categoryCompatible(provider: ProviderModel, category: GarmentCategory?): Boolean {
    if (category == null || category == GarmentCategory.UNKNOWN) return true
    val declared = provider.garmentCategories
    return declared.isEmpty() || category.wire in declared
}

fun compatibleProviders(
    providers: List<ProviderModel>,
    category: GarmentCategory?,
): List<ProviderModel> = selectableProviders(providers).filter { categoryCompatible(it, category) }

fun candidateLimit(provider: ProviderModel?): Int =
    (provider?.maxCandidates ?: MAX_CANDIDATES).coerceIn(MIN_CANDIDATES, MAX_CANDIDATES)

fun candidateCountFixedMessage(provider: ProviderModel?): String? =
    if (candidateLimit(provider) == MIN_CANDIDATES) {
        "该 Provider 当前固定生成 1 张候选。"
    } else {
        null
    }

fun clampCandidateCount(requested: Int, provider: ProviderModel?): Int =
    requested.coerceIn(MIN_CANDIDATES, candidateLimit(provider))

fun defaultProvider(providers: List<ProviderModel>): ProviderModel? =
    providers.firstOrNull { it.isDefault && it.selectable }
        ?: providers.firstOrNull { it.selectable }

fun maskCompatibleProviders(providers: List<ProviderModel>): List<ProviderModel> =
    selectableProviders(providers).filter { it.supportsManualMask }

fun generationBlockingReason(state: CreateWizardUiState): String? {
    if (state.step != WizardStep.SETTINGS || state.selectedProvider != null) return null
    if (state.loading) return "正在检查可用 Provider，请稍候。"
    state.providerError?.let { return "无法读取 Provider：${it.detail}" }
    if (state.providers.isEmpty()) {
        return "当前没有已启用的 Provider，请先在管理端完成配置。"
    }
    val categoryMatches = state.providers.filter {
        categoryCompatible(it, state.garmentCategory)
    }
    if (categoryMatches.isEmpty()) {
        return "当前 Provider 不支持所选衣物类别，请返回上一步更换类别或联系管理员。"
    }
    val reason = categoryMatches.firstNotNullOfOrNull { it.unavailableReason }
    return reason ?: "当前没有可用 Provider，请管理员检查配置后重新验证。"
}
