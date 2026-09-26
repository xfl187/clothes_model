package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.ProviderConfig
import com.clothesmodel.contract.model.ProviderConfigPage
import com.clothesmodel.contract.model.ProviderConfigRequest
import com.clothesmodel.contract.model.ProviderPage
import com.clothesmodel.contract.model.ProviderValidationResult

interface ProvidersApi {
    /**
     * POST api/v1/admin/provider-configs
     * Save a new inactive provider configuration without changing the default
     * 
     * Responses:
     *  - 201: Inactive provider configuration created; secret value is not returned.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param idempotencyKey Opaque client-generated key. Reusing a key with a different payload returns idempotency_key_reused.
     * @param providerConfigRequest 
     * @return [ProviderConfig]
     */
    @POST("api/v1/admin/provider-configs")
    suspend fun createProviderConfig(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body providerConfigRequest: ProviderConfigRequest): Response<ProviderConfig>

    /**
     * POST api/v1/admin/provider-configs/{provider_id}/enable
     * Enable a validated provider configuration without changing the default
     * 
     * Responses:
     *  - 200: Provider configuration enabled.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @param idempotencyKey Opaque client-generated key. Reusing a key with a different payload returns idempotency_key_reused.
     * @return [ProviderConfig]
     */
    @POST("api/v1/admin/provider-configs/{provider_id}/enable")
    suspend fun enableProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ProviderConfig>

    /**
     * GET api/v1/admin/provider-configs/{provider_id}
     * Read a redacted provider configuration and capability snapshot
     * 
     * Responses:
     *  - 200: Redacted provider configuration.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @return [ProviderConfig]
     */
    @GET("api/v1/admin/provider-configs/{provider_id}")
    suspend fun getProviderConfig(@Path("provider_id") providerId: java.util.UUID): Response<ProviderConfig>

    /**
     * GET api/v1/providers
     * List providers and capability snapshots available for new jobs
     * 
     * Responses:
     *  - 200: Provider page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @return [ProviderPage]
     */
    @GET("api/v1/providers")
    suspend fun listAvailableProviders(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50): Response<ProviderPage>

    /**
     * GET api/v1/admin/provider-configs
     * List redacted provider configurations
     * 
     * Responses:
     *  - 200: Provider configuration page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @return [ProviderConfigPage]
     */
    @GET("api/v1/admin/provider-configs")
    suspend fun listProviderConfigs(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50): Response<ProviderConfigPage>

    /**
     * PATCH api/v1/admin/provider-configs/{provider_id}
     * Create the next immutable configuration revision
     * 
     * Responses:
     *  - 200: New configuration revision saved without changing the default.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @param providerConfigRequest 
     * @return [ProviderConfig]
     */
    @PATCH("api/v1/admin/provider-configs/{provider_id}")
    suspend fun updateProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Body providerConfigRequest: ProviderConfigRequest): Response<ProviderConfig>

    /**
     * POST api/v1/admin/provider-configs/{provider_id}/validate
     * Run connection, capability, and minimal generation checks
     * 
     * Responses:
     *  - 200: Validation result; testing does not enable or select the provider.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @param idempotencyKey Opaque client-generated key. Reusing a key with a different payload returns idempotency_key_reused.
     * @return [ProviderValidationResult]
     */
    @POST("api/v1/admin/provider-configs/{provider_id}/validate")
    suspend fun validateProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ProviderValidationResult>

}
