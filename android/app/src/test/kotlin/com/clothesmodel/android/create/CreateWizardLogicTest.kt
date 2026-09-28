package com.clothesmodel.android.create

import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.ProviderAvailabilityDomain
import com.clothesmodel.android.data.ProviderModel
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
) = ProviderModel(
    id = UUID.randomUUID(),
    displayName = name,
    availability = availability,
    isDefault = isDefault,
    maxCandidates = maxCandidates,
    supportsManualMask = mask,
    supportsRegionMask = mask,
    garmentCategories = categories,
    unavailableReason = null,
)

class CreateWizardLogicTest {
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
}
