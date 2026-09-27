package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.FinishFailedRequest
import com.clothesmodel.contract.model.JobCommandResult
import com.clothesmodel.contract.model.JobItem
import com.clothesmodel.contract.model.JobPage
import com.clothesmodel.contract.model.JobState
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.RetryJobItemRequest
import com.clothesmodel.contract.model.TryOnJob

interface JobsApi {
    /**
     * POST api/v1/jobs/{job_id}/cancel
     * Best-effort cancel every unfinished candidate while retaining successful outputs
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
    @POST("api/v1/jobs/{job_id}/cancel")
    suspend fun cancelJob(@Path("job_id") jobId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/job-items/{job_item_id}/cancel
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
    @POST("api/v1/job-items/{job_item_id}/cancel")
    suspend fun cancelJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/jobs
     * Create a try-on job and lock generation configuration versions
     * 
     * Responses:
     *  - 201: Persisted job, including locked Provider and Workflow references.
     *  - 401: Authentication is missing or invalid.
     *  - 409: The selected provider is disabled, unavailable, or capability-incompatible.
     *  - 422: Request failed with a stable machine-readable error code.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param createJobRequest 
     * @return [TryOnJob]
     */
    @POST("api/v1/jobs")
    suspend fun createJob(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body createJobRequest: CreateJobRequest): Response<TryOnJob>

    /**
     * POST api/v1/job-items/{job_item_id}/finish-failed
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
    @POST("api/v1/job-items/{job_item_id}/finish-failed")
    suspend fun finishJobItemAsFailed(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body finishFailedRequest: FinishFailedRequest): Response<JobCommandResult>

    /**
     * GET api/v1/jobs/{job_id}
     * Read authoritative job, item, output, and locked-version state
     * 
     * Responses:
     *  - 200: Job details.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param jobId 
     * @return [TryOnJob]
     */
    @GET("api/v1/jobs/{job_id}")
    suspend fun getJob(@Path("job_id") jobId: java.util.UUID): Response<TryOnJob>

    /**
     * GET api/v1/job-items/{job_item_id}
     * Read one candidate execution and its immutable attempt lineage
     * 
     * Responses:
     *  - 200: Job item.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param jobItemId 
     * @return [JobItem]
     */
    @GET("api/v1/job-items/{job_item_id}")
    suspend fun getJobItem(@Path("job_item_id") jobItemId: java.util.UUID): Response<JobItem>

    /**
     * GET api/v1/jobs
     * List jobs ordered by created_at and id
     * 
     * Responses:
     *  - 200: Job page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @param state  (optional)
     * @return [JobPage]
     */
    @GET("api/v1/jobs")
    suspend fun listJobs(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50, @Query("state") state: JobState? = null): Response<JobPage>

    /**
     * POST api/v1/job-items/{job_item_id}/requery
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
    @POST("api/v1/job-items/{job_item_id}/requery")
    suspend fun requeryJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<JobCommandResult>

    /**
     * POST api/v1/job-items/{job_item_id}/retry
     * Create a new traceable JobItem attempt without overwriting the original
     * 
     * Responses:
     *  - 201: New JobItem created in queued state and aggregate job recalculated.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param jobItemId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param retryJobItemRequest  (optional)
     * @return [JobCommandResult]
     */
    @POST("api/v1/job-items/{job_item_id}/retry")
    suspend fun retryJobItem(@Path("job_item_id") jobItemId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body retryJobItemRequest: RetryJobItemRequest? = null): Response<JobCommandResult>

}
