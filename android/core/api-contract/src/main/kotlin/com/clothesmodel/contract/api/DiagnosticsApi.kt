package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.DiagnosticJobDetail
import com.clothesmodel.contract.model.DiagnosticJobPage
import com.clothesmodel.contract.model.JobState
import com.clothesmodel.contract.model.ProblemDetails

interface DiagnosticsApi {
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
