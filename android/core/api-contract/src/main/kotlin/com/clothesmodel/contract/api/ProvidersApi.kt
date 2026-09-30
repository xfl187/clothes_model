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
     * POST api/v1/admin/provider-configs/{provider_id}/archive
     * Archive a Provider while preserving revisions and job history
     * Moves a non-system, non-default Provider to the disabled state. Archived Providers remain readable by Admin and by existing locked jobs, but are excluded from new job selection. Repeating the operation is safe.
     * Responses:
     *  - 200: Provider archived; credentials and historical references are retained.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [ProviderConfig]
     */
    @POST("api/v1/admin/provider-configs/{provider_id}/archive")
    suspend fun archiveProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ProviderConfig>

    /**
     * POST api/v1/admin/provider-configs
     * Save a new inactive provider configuration without changing the default
     * 
     * Responses:
     *  - 201: Inactive provider configuration created; secret value is not returned.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param providerConfigRequest 
     * @return [ProviderConfig]
     */
    @POST("api/v1/admin/provider-configs")
    suspend fun createProviderConfig(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body providerConfigRequest: ProviderConfigRequest): Response<ProviderConfig>

    /**
     * DELETE api/v1/admin/provider-configs/{provider_id}
     * Permanently delete an unreferenced provider configuration
     * Deletes the configuration and all of its immutable revisions. The system-managed ComfyUI provider, the current default, and configurations referenced by job history cannot be deleted.
     * Responses:
     *  - 204: Provider configuration deleted.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @return [Unit]
     */
    @DELETE("api/v1/admin/provider-configs/{provider_id}")
    suspend fun deleteProviderConfig(@Path("provider_id") providerId: java.util.UUID): Response<Unit>

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
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
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
     * POST api/v1/admin/provider-configs/{provider_id}/restore
     * Restore an archived Provider to inactive state
     * Restores a disabled Provider as inactive. It must be validated and enabled again before it can be selected as the default or used for new jobs.
     * Responses:
     *  - 200: Provider restored to inactive state.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param providerId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [ProviderConfig]
     */
    @POST("api/v1/admin/provider-configs/{provider_id}/restore")
    suspend fun restoreProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ProviderConfig>

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
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [ProviderValidationResult]
     */
    @POST("api/v1/admin/provider-configs/{provider_id}/validate")
    suspend fun validateProviderConfig(@Path("provider_id") providerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ProviderValidationResult>

}
