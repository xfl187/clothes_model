package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.CleanupRequest
import com.clothesmodel.contract.model.CleanupResult
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.StorageScanRequest
import com.clothesmodel.contract.model.StorageScanResult
import com.clothesmodel.contract.model.StorageStatus

interface StorageApi {
    /**
     * POST api/v1/admin/storage/cleanup
     * Delete files from a confirmed scan while preserving protected references
     * 
     * Responses:
     *  - 200: Cleanup result.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param idempotencyKey Opaque client-generated key. Reusing a key with a different payload returns idempotency_key_reused.
     * @param cleanupRequest 
     * @return [CleanupResult]
     */
    @POST("api/v1/admin/storage/cleanup")
    suspend fun cleanupStorage(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body cleanupRequest: CleanupRequest): Response<CleanupResult>

    /**
     * GET api/v1/admin/storage
     * Read capacity and whether new uploads and jobs are accepted
     * 
     * Responses:
     *  - 200: Storage status.
     *  - 401: Authentication is missing or invalid.
     *
     * @return [StorageStatus]
     */
    @GET("api/v1/admin/storage")
    suspend fun getStorageStatus(): Response<StorageStatus>

    /**
     * POST api/v1/admin/storage/scan
     * Preview reclaimable files without deleting content
     * 
     * Responses:
     *  - 200: Cleanup preview including protected references.
     *  - 401: Authentication is missing or invalid.
     *
     * @param idempotencyKey Opaque client-generated key. Reusing a key with a different payload returns idempotency_key_reused.
     * @param storageScanRequest  (optional)
     * @return [StorageScanResult]
     */
    @POST("api/v1/admin/storage/scan")
    suspend fun scanStorage(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body storageScanRequest: StorageScanRequest? = null): Response<StorageScanResult>

}
