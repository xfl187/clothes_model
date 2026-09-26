package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.ComfyNodeConfiguration
import com.clothesmodel.contract.model.ComfyNodeConfigurationRequest
import com.clothesmodel.contract.model.ConnectionTestResult
import com.clothesmodel.contract.model.DefaultProviderConfiguration
import com.clothesmodel.contract.model.DefaultProviderUpdateRequest
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.RetentionPolicy
import com.clothesmodel.contract.model.RetentionPolicyUpdateRequest

interface AdminConfigurationApi {
    /**
     * GET api/v1/admin/configuration/comfy-node
     * Read the single redacted ComfyUI node configuration
     * 
     * Responses:
     *  - 200: Redacted node configuration.
     *  - 401: Authentication is missing or invalid.
     *
     * @return [ComfyNodeConfiguration]
     */
    @GET("api/v1/admin/configuration/comfy-node")
    suspend fun getComfyNodeConfiguration(): Response<ComfyNodeConfiguration>

    /**
     * GET api/v1/admin/configuration/default-provider
     * Read the Provider selection applied to new jobs
     * 
     * Responses:
     *  - 200: Current default Provider configuration.
     *  - 401: Authentication is missing or invalid.
     *
     * @return [DefaultProviderConfiguration]
     */
    @GET("api/v1/admin/configuration/default-provider")
    suspend fun getDefaultProviderConfiguration(): Response<DefaultProviderConfiguration>

    /**
     * GET api/v1/admin/configuration/retention
     * Read runtime retention policy
     * 
     * Responses:
     *  - 200: Current retention policy.
     *  - 401: Authentication is missing or invalid.
     *
     * @return [RetentionPolicy]
     */
    @GET("api/v1/admin/configuration/retention")
    suspend fun getRetentionPolicy(): Response<RetentionPolicy>

    /**
     * POST api/v1/admin/configuration/comfy-node/test
     * Test connectivity without enabling the node or changing locked jobs
     * 
     * Responses:
     *  - 200: Connection test result.
     *  - 401: Authentication is missing or invalid.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [ConnectionTestResult]
     */
    @POST("api/v1/admin/configuration/comfy-node/test")
    suspend fun testComfyNodeConnection(@Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<ConnectionTestResult>

    /**
     * PUT api/v1/admin/configuration/comfy-node
     * Replace the single ComfyUI physical-node configuration
     * 
     * Responses:
     *  - 200: Node configuration saved; credentials are not returned.
     *  - 401: Authentication is missing or invalid.
     *
     * @param comfyNodeConfigurationRequest 
     * @return [ComfyNodeConfiguration]
     */
    @PUT("api/v1/admin/configuration/comfy-node")
    suspend fun updateComfyNodeConfiguration(@Body comfyNodeConfigurationRequest: ComfyNodeConfigurationRequest): Response<ComfyNodeConfiguration>

    /**
     * PUT api/v1/admin/configuration/default-provider
     * Change the default for new jobs without modifying existing locked jobs
     * 
     * Responses:
     *  - 200: Default Provider updated for new jobs only.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param defaultProviderUpdateRequest 
     * @return [DefaultProviderConfiguration]
     */
    @PUT("api/v1/admin/configuration/default-provider")
    suspend fun updateDefaultProviderConfiguration(@Body defaultProviderUpdateRequest: DefaultProviderUpdateRequest): Response<DefaultProviderConfiguration>

    /**
     * PUT api/v1/admin/configuration/retention
     * Update future cleanup eligibility rules
     * 
     * Responses:
     *  - 200: Retention policy updated.
     *  - 401: Authentication is missing or invalid.
     *
     * @param retentionPolicyUpdateRequest 
     * @return [RetentionPolicy]
     */
    @PUT("api/v1/admin/configuration/retention")
    suspend fun updateRetentionPolicy(@Body retentionPolicyUpdateRequest: RetentionPolicyUpdateRequest): Response<RetentionPolicy>

}
