package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.DiagnosticJobDetail
import com.clothesmodel.contract.model.DiagnosticJobPage
import com.clothesmodel.contract.model.FinishFailedRequest
import com.clothesmodel.contract.model.JobCommandResult
import com.clothesmodel.contract.model.JobState
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.RetryJobItemRequest

interface DiagnosticsApi {
    /**
     * POST api/v1/admin/diagnostics/jobs/{job_id}/cancel
     * Best-effort cancel every unfinished candidate for an administrator
     * 
     * Responses:
     *  - 200: Updated aggregate job state.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [JobCommandResult]
     */
    @POST("api/v1/admin/diagnostics/jobs/{job_id}/cancel")
    suspend fun adminCancelJob(@Path("job_id") jobId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/admin/diagnostics/job-items/{job_item_id}/cancel
     * Best-effort cancel one unfinished candidate without affecting others
     * 
     * Responses:
     *  - 200: Updated aggregate job state.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobItemId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [JobCommandResult]
     */
    @POST("api/v1/admin/diagnostics/job-items/{job_item_id}/cancel")
    suspend fun adminCancelJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/admin/diagnostics/job-items/{job_item_id}/finish-failed
     * End needs_attention processing as a retained failure
     * 
     * Responses:
     *  - 200: JobItem ended as failed and aggregate job recalculated.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobItemId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param finishFailedRequest 
     * @return [JobCommandResult]
     */
    @POST("api/v1/admin/diagnostics/job-items/{job_item_id}/finish-failed")
    suspend fun adminFinishJobItemAsFailed(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body finishFailedRequest: FinishFailedRequest): Response<JobCommandResult>

    /**
     * POST api/v1/admin/diagnostics/job-items/{job_item_id}/requery
     * Requery an uncertain external execution without starting a new one
     * 
     * Responses:
     *  - 200: Job synchronized with the known external state.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobItemId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [JobCommandResult]
     */
    @POST("api/v1/admin/diagnostics/job-items/{job_item_id}/requery")
    suspend fun adminRequeryJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/admin/diagnostics/job-items/{job_item_id}/retry
     * Create a new traceable JobItem attempt without overwriting the original
     * 
     * Responses:
     *  - 201: New JobItem created and aggregate job recalculated.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobItemId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param retryJobItemRequest  (optional)
     * @return [JobCommandResult]
     */
    @POST("api/v1/admin/diagnostics/job-items/{job_item_id}/retry")
    suspend fun adminRetryJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body retryJobItemRequest: RetryJobItemRequest? = null): Response<JobCommandResult>

    /**
     * GET api/v1/admin/diagnostics/jobs/{job_id}
     * Read redacted lineage, locked versions, errors, and external execution metadata
     * 
     * Responses:
     *  - 200: Redacted diagnostic details.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param jobId 
     * @return [DiagnosticJobDetail]
     */
    @GET("api/v1/admin/diagnostics/jobs/{job_id}")
    suspend fun getDiagnosticJob(@Path("job_id") jobId: java.util.UUID): Response<DiagnosticJobDetail>

    /**
     * GET api/v1/admin/diagnostics/jobs
     * List redacted job diagnostics from a timestamped snapshot
     * 
     * Responses:
     *  - 200: Diagnostic job page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @param state  (optional)
     * @return [DiagnosticJobPage]
     */
    @GET("api/v1/admin/diagnostics/jobs")
    suspend fun listDiagnosticJobs(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50, @Query("state") state: JobState? = null): Response<DiagnosticJobPage>

}
