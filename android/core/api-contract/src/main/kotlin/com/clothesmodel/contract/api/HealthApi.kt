package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.HealthStatus
import com.clothesmodel.contract.model.ProblemDetails

interface HealthApi {
    /**
     * GET health/live
     * Report whether the process is alive
     * 
     * Responses:
     *  - 200: Process is alive.
     *
     * @return [HealthStatus]
     */
    @GET("health/live")
    suspend fun getLiveness(): Response<HealthStatus>

    /**
     * GET health/ready
     * Report whether required local dependencies are ready
     * 
     * Responses:
     *  - 200: Required dependencies are ready.
     *  - 503: Request failed with a stable machine-readable error code.
     *
     * @return [HealthStatus]
     */
    @GET("health/ready")
    suspend fun getReadiness(): Response<HealthStatus>

}
