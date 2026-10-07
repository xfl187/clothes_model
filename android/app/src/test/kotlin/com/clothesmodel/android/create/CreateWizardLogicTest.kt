package com.clothesmodel.android.create

import com.clothesmodel.android.data.AssetLifecycle
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
import java.time.OffsetDateTime
import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun provider(
    name: String,
    availability: ProviderAvailabilityDomain = ProviderAvailabilityDomain.AVAILABLE,
    isDefault: Boolean = false,
    maxCandidates: Int = 4,
    mask: Boolean = false,
    categories: List<String> = emptyList(),
    unavailableReason: String? = null,
) = ProviderModel(
    id = UUID.randomUUID(),
    displayName = name,
    availability = availability,
    isDefault = isDefault,
    maxCandidates = maxCandidates,
    supportsManualMask = mask,
    supportsRegionMask = mask,
    garmentCategories = categories,
    unavailableReason = unavailableReason,
)

class CreateWizardLogicTest {
    @Test
    fun garmentStepFiltersAssetsBySelectedCategory() {
        fun asset(category: GarmentCategory) = AssetModel(
            id = UUID.randomUUID(),
            kind = "garment",
            favorite = false,
            lifecycle = AssetLifecycle.ACTIVE,
            contentAvailable = true,
            width = 100,
            height = 100,
            createdAt = OffsetDateTime.parse("2019-08-24T14:15:22Z"),
            garmentCategory = category,
            garmentSource = null,
            qualityWarnings = emptyList(),
        )
        val upper = asset(GarmentCategory.UPPER_BODY)
        val lower = asset(GarmentCategory.LOWER_BODY)

        assertEquals(
            listOf(lower),
            filterAssetsForStep(
                listOf(upper, lower),
                WizardStep.GARMENT,
                GarmentCategory.LOWER_BODY,
            ),
        )
    }

    @Test
    fun disabledAndMisconfiguredProvidersAreNotSelectable() {
        val providers = listOf(
            provider("a", ProviderAvailabilityDomain.DISABLED),
            provider("b", ProviderAvailabilityDomain.UNAVAILABLE_CONFIGURATION),
            provider("c", ProviderAvailabilityDomain.TEMPORARILY_OFFLINE),
            provider("d", ProviderAvailabilityDomain.AVAILABLE),
        )
        assertEquals(listOf("c", "d"), selectableProviders(providers).map { it.displayName })
    }

    @Test
    fun categoryCompatibilityUsesDeclaredValues() {
        val garmentOnly = provider("g", categories = listOf("upper_body"))
        assertTrue(categoryCompatible(garmentOnly, GarmentCategory.UPPER_BODY))
        assertFalse(categoryCompatible(garmentOnly, GarmentCategory.DRESS))
        val any = provider("any")
        assertTrue(categoryCompatible(any, GarmentCategory.DRESS))
        assertTrue(categoryCompatible(garmentOnly, GarmentCategory.UNKNOWN))
    }

    @Test
    fun candidateCountIsClampedToProviderLimit() {
        val limited = provider("limited", maxCandidates = 2)
        assertEquals(2, candidateLimit(limited))
        assertEquals(2, clampCandidateCount(9, limited))
        assertEquals(1, clampCandidateCount(0, limited))
        assertEquals(4, clampCandidateCount(9, null))
    }

    @Test
    fun singleCandidateProviderExplainsFixedCountInsteadOfOfferingDisabledControls() {
        val fixed = provider("fixed", maxCandidates = 1)
        val variable = provider("variable", maxCandidates = 2)

        assertEquals("该 Provider 当前固定生成 1 张候选。", candidateCountFixedMessage(fixed))
        assertNull(candidateCountFixedMessage(variable))
    }

    @Test
    fun defaultProviderPrefersMarkedDefaultThenFirstSelectable() {
        val disabled = provider("d", ProviderAvailabilityDomain.DISABLED, isDefault = true)
        val first = provider("a")
        val second = provider("b")
        assertEquals(first.id, defaultProvider(listOf(disabled, first, second))?.id)
        val marked = provider("m", isDefault = true)
        assertEquals(marked.id, defaultProvider(listOf(first, marked))?.id)
        assertNull(defaultProvider(listOf(disabled)))
    }

    @Test
    fun maskCompatibleProvidersRequireManualMask() {
        val withoutMask = provider("a")
        val withMask = provider("b", mask = true)
        assertEquals(listOf("b"), maskCompatibleProviders(listOf(withoutMask, withMask)).map { it.displayName })
    }

    @Test
    fun generationBlockingReasonExplainsUnavailableProvider() {
        val state = CreateWizardUiState(
            step = WizardStep.SETTINGS,
            loading = false,
            providers = listOf(
                provider(
                    "Ark",
                    ProviderAvailabilityDomain.UNAVAILABLE_CONFIGURATION,
                    unavailableReason = "Provider 凭据无法解密，请管理员重新保存 API Key。",
                ),
            ),
        )

        assertEquals(
            "Provider 凭据无法解密，请管理员重新保存 API Key。",
            generationBlockingReason(state),
        )
    }
}
