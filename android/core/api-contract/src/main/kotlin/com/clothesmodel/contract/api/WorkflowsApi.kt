package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.WorkflowActivateRequest
import com.clothesmodel.contract.model.WorkflowCreateRequest
import com.clothesmodel.contract.model.WorkflowPage
import com.clothesmodel.contract.model.WorkflowRetireRequest
import com.clothesmodel.contract.model.WorkflowValidationResult
import com.clothesmodel.contract.model.WorkflowVersion

interface WorkflowsApi {
    /**
     * POST api/v1/admin/workflows/{workflow_version_id}/activate
     * Activate or roll back to a compatible validated version for new jobs
     * Activating a validated draft, validated version, or previously retired immutable version atomically retires the prior active version for the same mode. This is the rollback operation. Existing jobs retain their locked Provider and Workflow versions.
     * Responses:
     *  - 200: Workflow version activated; existing jobs retain their locked version.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param workflowVersionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param workflowActivateRequest 
     * @return [WorkflowVersion]
     */
    @POST("api/v1/admin/workflows/{workflow_version_id}/activate")
    suspend fun activateWorkflowVersion(@Path("workflow_version_id") workflowVersionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body workflowActivateRequest: WorkflowActivateRequest): Response<WorkflowVersion>

    /**
     * POST api/v1/admin/workflows
     * Upload a new immutable draft Workflow version
     * 
     * Responses:
     *  - 201: Draft Workflow version created; existing versions are unchanged.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *  - 422: Request failed with a stable machine-readable error code.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param workflowCreateRequest 
     * @return [WorkflowVersion]
     */
    @POST("api/v1/admin/workflows")
    suspend fun createWorkflowVersion(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body workflowCreateRequest: WorkflowCreateRequest): Response<WorkflowVersion>

    /**
     * GET api/v1/admin/workflows/{workflow_version_id}
     * Read an immutable Workflow version and its validation state
     * 
     * Responses:
     *  - 200: Workflow version.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param workflowVersionId 
     * @return [WorkflowVersion]
     */
    @GET("api/v1/admin/workflows/{workflow_version_id}")
    suspend fun getWorkflowVersion(@Path("workflow_version_id") workflowVersionId: java.util.UUID): Response<WorkflowVersion>

    /**
     * GET api/v1/admin/workflows
     * List immutable Workflow versions
     * 
     * Responses:
     *  - 200: Workflow version page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @return [WorkflowPage]
     */
    @GET("api/v1/admin/workflows")
    suspend fun listWorkflowVersions(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50): Response<WorkflowPage>

    /**
     * POST api/v1/admin/workflows/{workflow_version_id}/retire
     * Retire an active or validated Workflow for future jobs without changing history
     * Retirement prevents the version from being selected for new jobs. Existing jobs keep their locked Workflow and may continue on a compatible replacement physical node. A retired immutable version may later be activated again as an explicit rollback.
     * Responses:
     *  - 200: Workflow retired for future jobs only.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param workflowVersionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param workflowRetireRequest 
     * @return [WorkflowVersion]
     */
    @POST("api/v1/admin/workflows/{workflow_version_id}/retire")
    suspend fun retireWorkflowVersion(@Path("workflow_version_id") workflowVersionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body workflowRetireRequest: WorkflowRetireRequest): Response<WorkflowVersion>

    /**
     * POST api/v1/admin/workflows/{workflow_version_id}/validate
     * Validate bindings, capabilities, compatibility, and minimal test execution
     * 
     * Responses:
     *  - 200: Workflow validation result.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *  - 422: Request failed with a stable machine-readable error code.
     *  - 507: New uploads or jobs are blocked because storage capacity is insufficient.
     *
     * @param workflowVersionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [WorkflowValidationResult]
     */
    @POST("api/v1/admin/workflows/{workflow_version_id}/validate")
    suspend fun validateWorkflowVersion(@Path("workflow_version_id") workflowVersionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<WorkflowValidationResult>

}
