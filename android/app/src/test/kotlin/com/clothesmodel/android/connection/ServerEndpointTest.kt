package com.clothesmodel.android.connection

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ServerEndpointTest {
    @Test fun normalizesHttps() {
        assertEquals("https://example.com/api/", ServerEndpoint.normalize(" example.com/api/ "))
    }

    @Test fun rejectsHttpOutsideExplicitLocalDebugPolicy() {
        assertThrows(IllegalArgumentException::class.java) { ServerEndpoint.normalize("http://example.com") }
        assertThrows(IllegalArgumentException::class.java) { ServerEndpoint.normalize("http://10.0.2.2") }
        assertEquals(
            "http://10.0.2.2:8000/",
            ServerEndpoint.normalize("http://10.0.2.2:8000", setOf("10.0.2.2")),
        )
    }

    @Test fun rejectsCredentialsAndFragments() {
        assertThrows(IllegalArgumentException::class.java) { ServerEndpoint.normalize("https://user@example.com") }
        assertThrows(IllegalArgumentException::class.java) { ServerEndpoint.normalize("https://example.com/#secret") }
    }

    @Test fun classifiesAuthenticationAndAvailabilityFailures() {
        assertEquals(ConnectionResult.Connected, classifyConnectionStatus(200))
        assertEquals(ConnectionResult.InvalidToken, classifyConnectionStatus(401))
        assertEquals(ConnectionResult.WrongScope, classifyConnectionStatus(403))
        assertEquals(ConnectionResult.Unavailable, classifyConnectionStatus(503))
    }
}
