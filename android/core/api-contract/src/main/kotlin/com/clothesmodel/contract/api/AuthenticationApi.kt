package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.AdminSession
import com.clothesmodel.contract.model.AdminSessionCreateRequest
import com.clothesmodel.contract.model.AppAuthStatus
import com.clothesmodel.contract.model.AppCredentialRotation
import com.clothesmodel.contract.model.AppCredentialStatus
import com.clothesmodel.contract.model.ProblemDetails

interface AuthenticationApi {
    /**
     * POST api/v1/admin/auth/session
     * Exchange the Admin Token for a secure browser session
     * 
     * Responses:
     *  - 201: Session created. The session identifier is set in an HttpOnly cookie.
     *  - 401: Authentication is missing or invalid.
     *  - 429: Authentication attempts are temporarily throttled.
     *
     * @param adminSessionCreateRequest 
     * @return [AdminSession]
     */
    @POST("api/v1/admin/auth/session")
    suspend fun createAdminSession(@Body adminSessionCreateRequest: AdminSessionCreateRequest): Response<AdminSession>

    /**
     * DELETE api/v1/admin/auth/session
     * End the current admin browser session
     * 
     * Responses:
     *  - 204: Session ended.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The admin write was rejected by CSRF or same-origin validation.
     *
     * @return [Unit]
     */
    @DELETE("api/v1/admin/auth/session")
    suspend fun deleteAdminSession(): Response<Unit>

    /**
     * GET api/v1/admin/auth/session
     * Restore an authenticated Admin browser session and refresh its CSRF value
     * Uses the HttpOnly session cookie. The returned CSRF value is short-lived client state for memory-only use and must not be persisted in browser storage.
     * Responses:
     *  - 200: Session is active and a current CSRF value is returned.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *
     * @return [AdminSession]
     */
    @GET("api/v1/admin/auth/session")
    suspend fun getAdminSession(): Response<AdminSession>

    /**
     * GET api/v1/auth/status
     * Validate the App Token without returning secret material
     * 
     * Responses:
     *  - 200: App Token is valid.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *
     * @return [AppAuthStatus]
     */
    @GET("api/v1/auth/status")
    suspend fun getAppAuthStatus(): Response<AppAuthStatus>

    /**
     * GET api/v1/admin/app-credential
     * Read App Token metadata without exposing the token value
     * 
     * Responses:
     *  - 200: App credential metadata; never the token value.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *
     * @return [AppCredentialStatus]
     */
    @GET("api/v1/admin/app-credential")
    suspend fun getAppCredentialStatus(): Response<AppCredentialStatus>

    /**
     * POST api/v1/admin/app-credential
     * Rotate the App Token, invalidating the previous token and returning the new value once
     * Immediately revokes all active App Tokens and issues one new token. Server-side work is not cancelled. The new plaintext token is returned exactly once and cannot be read again.
     * Responses:
     *  - 200: New App Token returned once; the previous token is invalid immediately.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The admin write was rejected by CSRF or same-origin validation.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @return [AppCredentialRotation]
     */
    @POST("api/v1/admin/app-credential")
    suspend fun rotateAppCredential(@Header("Idempotency-Key") idempotencyKey: kotlin.String): Response<AppCredentialRotation>

}
