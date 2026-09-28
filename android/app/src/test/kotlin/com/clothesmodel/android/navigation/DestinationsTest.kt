package com.clothesmodel.android.navigation

import org.junit.Assert.assertEquals
import org.junit.Test

class DestinationsTest {
    @Test
    fun tabRoutes_areFixedHomeAssetsHistory() {
        assertEquals(listOf("首页", "素材", "历史"), Destinations.tabRoutes.map { it.second })
        assertEquals(
            listOf(Destinations.HOME, Destinations.ASSETS, Destinations.HISTORY),
            Destinations.tabRoutes.map { it.first },
        )
    }

    @Test
    fun detailRoutes_passOnlyIdentifiers() {
        assertEquals("assets/abc", Destinations.assetDetail("abc"))
        assertEquals("jobs/abc", Destinations.jobDetail("abc"))
        assertEquals("jobs/abc/results", Destinations.results("abc"))
        assertEquals("jobs/abc/compare/c1", Destinations.compare("abc", "c1"))
        assertEquals("jobs/abc/mask/c1", Destinations.mask("abc", "c1"))
    }

    @Test
    fun connectionRoute_defaultsToNoReauthentication() {
        assertEquals("connection?reauth=false", Destinations.connection())
        assertEquals("connection?reauth=true", Destinations.connection(reauth = true))
    }
}
