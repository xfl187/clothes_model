package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.Asset
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.UploadChunkResult
import com.clothesmodel.contract.model.UploadCompleteRequest
import com.clothesmodel.contract.model.UploadCreateRequest
import com.clothesmodel.contract.model.UploadSession

import okhttp3.MultipartBody

interface UploadsApi {
    /**
     * PATCH api/v1/uploads/{upload_id}/content
     * Append bytes at the server-confirmed upload offset
     * 
     * Responses:
     *  - 200: Bytes appended.
     *  - 401: Authentication is missing or invalid.
     *  - 409: The supplied upload offset does not match the confirmed server offset.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param uploadId 
     * @param uploadOffset 
     * @param body 
     * @return [UploadChunkResult]
     */
    @PATCH("api/v1/uploads/{upload_id}/content")
    suspend fun appendUploadContent(@Path("upload_id") uploadId: java.util.UUID, @Header("Upload-Offset") uploadOffset: kotlin.Long, @Body body: java.io.File): Response<UploadChunkResult>

    /**
     * DELETE api/v1/uploads/{upload_id}
     * Cancel an incomplete upload and discard temporary bytes
     * 
     * Responses:
     *  - 200: Upload cancelled or already terminal.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param uploadId 
     * @return [UploadSession]
     */
    @DELETE("api/v1/uploads/{upload_id}")
    suspend fun cancelUploadSession(@Path("upload_id") uploadId: java.util.UUID): Response<UploadSession>

    /**
     * POST api/v1/uploads/{upload_id}/complete
     * Validate uploaded content and create or rehydrate its logical Asset
     * 
     * Responses:
     *  - 201: Upload completed and a new or rehydrated Asset returned.
     *  - 401: Authentication is missing or invalid.
     *  - 409: The idempotency key was already bound to a different request.
     *  - 422: Uploaded bytes do not satisfy the private image boundary.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param uploadId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param uploadCompleteRequest 
     * @return [Asset]
     */
    @POST("api/v1/uploads/{upload_id}/complete")
    suspend fun completeUploadSession(@Path("upload_id") uploadId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body uploadCompleteRequest: UploadCompleteRequest): Response<Asset>

    /**
     * POST api/v1/uploads
     * Create a resumable upload session
     * 
     * Responses:
     *  - 201: Upload session created.
     *  - 401: Authentication is missing or invalid.
     *  - 409: The idempotency key was already bound to a different request.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param uploadCreateRequest 
     * @return [UploadSession]
     */
    @POST("api/v1/uploads")
    suspend fun createUploadSession(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body uploadCreateRequest: UploadCreateRequest): Response<UploadSession>

    /**
     * GET api/v1/uploads/{upload_id}
     * Read resumable upload progress
     * 
     * Responses:
     *  - 200: Current upload state.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param uploadId 
     * @return [UploadSession]
     */
    @GET("api/v1/uploads/{upload_id}")
    suspend fun getUploadSession(@Path("upload_id") uploadId: java.util.UUID): Response<UploadSession>

}
