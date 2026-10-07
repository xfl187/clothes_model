package com.clothesmodel.android.data

import android.content.Context
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.AssetsApi
import com.clothesmodel.contract.api.JobsApi
import com.clothesmodel.contract.api.OutfitsApi
import com.clothesmodel.contract.api.ProvidersApi
import com.clothesmodel.contract.api.UploadsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.infrastructure.Serializer
import com.clothesmodel.contract.model.ProblemDetails
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.ResponseBody

sealed interface Outcome<out T> {
    data class Success<T>(val value: T) : Outcome<T>
    data class Problem(val problem: ProblemModel) : Outcome<Nothing>
    data object AuthenticationExpired : Outcome<Nothing>
}

interface AuthenticationEvents {
    suspend fun onAuthenticationExpired()
}

data class ApiServices(
    val assets: AssetsApi,
    val jobs: JobsApi,
    val providers: ProvidersApi,
    val uploads: UploadsApi,
    val outfits: OutfitsApi,
)

interface ApiServicesFactory {
    suspend fun services(): ApiServices?
}

class ConnectionApiServicesFactory(
    context: Context,
    private val events: AuthenticationEvents,
) : ApiServicesFactory {
    private val appContext = context.applicationContext

    override suspend fun services(): ApiServices? {
        val vault = TokenVault(appContext)
        val store = ConnectionStore(appContext, vault)
        val connection = store.snapshot()
        val serverUrl = connection.serverUrl ?: return null
        val token = vault.read() ?: return null
        val client = ApiClient(baseUrl = serverUrl, authName = "AppBearer", bearerToken = token)
        return ApiServices(
            assets = client.createService(AssetsApi::class.java),
            jobs = client.createService(JobsApi::class.java),
            providers = client.createService(ProvidersApi::class.java),
            uploads = client.createService(UploadsApi::class.java),
            outfits = client.createService(OutfitsApi::class.java),
        )
    }
}

object ProblemParser {
    fun from(errorBody: ResponseBody?): ProblemModel {
        val fallback = ProblemModel(
            code = "request_failed",
            detail = "请求无法完成，请稍后重试。",
            status = 0,
            retryable = true,
        )
        val raw = runCatching { errorBody?.string() }.getOrNull() ?: return fallback
        val parsed = runCatching {
            Serializer.kotlinxSerializationJson.decodeFromString(ProblemDetails.serializer(), raw)
        }.getOrNull() ?: return fallback
        val referenceCount = parsed.context["reference_count"]?.jsonPrimitive?.intOrNull
        return ProblemModel(
            code = parsed.code,
            detail = parsed.detail,
            status = parsed.status,
            retryable = parsed.retryable,
            referenceCount = referenceCount,
        )
    }
}

fun networkProblem(): ProblemModel = ProblemModel(
    code = "network_unavailable",
    detail = "网络不可用，请稍后重试。",
    status = 0,
    retryable = true,
)
