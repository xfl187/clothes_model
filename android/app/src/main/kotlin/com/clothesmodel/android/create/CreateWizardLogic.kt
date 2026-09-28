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

fun clampCandidateCount(requested: Int, provider: ProviderModel?): Int =
    requested.coerceIn(MIN_CANDIDATES, candidateLimit(provider))

fun defaultProvider(providers: List<ProviderModel>): ProviderModel? =
    providers.firstOrNull { it.isDefault && it.selectable }
        ?: providers.firstOrNull { it.selectable }

fun maskCompatibleProviders(providers: List<ProviderModel>): List<ProviderModel> =
    selectableProviders(providers).filter { it.supportsManualMask }
