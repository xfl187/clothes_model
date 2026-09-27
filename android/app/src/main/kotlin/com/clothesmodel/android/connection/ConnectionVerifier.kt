package com.clothesmodel.android.connection

import com.clothesmodel.contract.api.AuthenticationApi
import com.clothesmodel.contract.infrastructure.ApiClient
import java.io.IOException

sealed interface ConnectionResult {
    data object Connected : ConnectionResult
    data object InvalidToken : ConnectionResult
    data object WrongScope : ConnectionResult
    data object Unavailable : ConnectionResult
}

internal fun classifyConnectionStatus(statusCode: Int): ConnectionResult = when (statusCode) {
    200 -> ConnectionResult.Connected
    401 -> ConnectionResult.InvalidToken
    403 -> ConnectionResult.WrongScope
    else -> ConnectionResult.Unavailable
}

class ConnectionVerifier {
    suspend fun verify(serverUrl: String, token: String): ConnectionResult = try {
        val response = ApiClient(
            baseUrl = serverUrl,
            authName = "AppBearer",
            bearerToken = token,
        ).createService(AuthenticationApi::class.java).getAppAuthStatus()
        classifyConnectionStatus(response.code())
    } catch (_: IOException) {
        ConnectionResult.Unavailable
    } catch (_: IllegalArgumentException) {
        ConnectionResult.Unavailable
    }
}
