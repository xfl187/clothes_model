package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.AddOutfitLayerRequest
import com.clothesmodel.contract.model.CreateOutfitBranchRequest
import com.clothesmodel.contract.model.CreateOutfitSessionRequest
import com.clothesmodel.contract.model.OutfitLayerResult
import com.clothesmodel.contract.model.OutfitSession
import com.clothesmodel.contract.model.OutfitSessionPage
import com.clothesmodel.contract.model.ProblemDetails
import com.clothesmodel.contract.model.ReapplyOutfitLayerRequest
import com.clothesmodel.contract.model.RemoveOutfitLayerRequest
import com.clothesmodel.contract.model.SelectOutfitRevisionRequest
import com.clothesmodel.contract.model.SwitchOutfitRouteRequest
import com.clothesmodel.contract.model.UpdateOutfitBranchRequest
import com.clothesmodel.contract.model.UpdateOutfitSessionRequest

interface OutfitsApi {
    /**
     * POST api/v1/outfits/{session_id}/branches/{branch_id}/layers
     * Add a garment layer by creating a linked single-garment try-on job
     * Requires a Provider that declares sequential layering and the target layer role. Adding a middle layer marks subsequent layers pending_reapply; no later task is created automatically.
     * Responses:
     *  - 201: Layer job created and linked to the session.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The selected provider is disabled, unavailable, or capability-incompatible.
     *
     * @param sessionId 
     * @param branchId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param addOutfitLayerRequest 
     * @return [OutfitLayerResult]
     */
    @POST("api/v1/outfits/{session_id}/branches/{branch_id}/layers")
    suspend fun addOutfitLayer(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body addOutfitLayerRequest: AddOutfitLayerRequest): Response<OutfitLayerResult>

    /**
     * POST api/v1/outfits/{session_id}/branches
     * Create a branch from an optional base revision or the original person image
     * 
     * Responses:
     *  - 201: Branch created; no generation task or fee is created.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param createOutfitBranchRequest  (optional)
     * @return [OutfitSession]
     */
    @POST("api/v1/outfits/{session_id}/branches")
    suspend fun createOutfitBranch(@Path("session_id") sessionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body createOutfitBranchRequest: CreateOutfitBranchRequest? = null): Response<OutfitSession>

    /**
     * POST api/v1/outfits
     * Create a layered-outfit session from one original person image
     * 
     * Responses:
     *  - 201: Session created with a locked layer-definition version and an initial main branch.
     *  - 401: Authentication is missing or invalid.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param createOutfitSessionRequest 
     * @return [OutfitSession]
     */
    @POST("api/v1/outfits")
    suspend fun createOutfitSession(@Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body createOutfitSessionRequest: CreateOutfitSessionRequest): Response<OutfitSession>

    /**
     * DELETE api/v1/outfits/{session_id}/branches/{branch_id}
     * Delete a branch without cascading into shared assets or other branches
     * 
     * Responses:
     *  - 200: Branch deleted; updated session returned.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param branchId 
     * @return [OutfitSession]
     */
    @DELETE("api/v1/outfits/{session_id}/branches/{branch_id}")
    suspend fun deleteOutfitBranch(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID): Response<OutfitSession>

    /**
     * DELETE api/v1/outfits/{session_id}
     * Delete a whole session after confirming revision and result impact
     * 
     * Responses:
     *  - 204: Session deleted; shared assets and other sessions are unchanged.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @return [Unit]
     */
    @DELETE("api/v1/outfits/{session_id}")
    suspend fun deleteOutfitSession(@Path("session_id") sessionId: java.util.UUID): Response<Unit>

    /**
     * GET api/v1/outfits/{session_id}
     * Read a session with its branches and current confirmed revision
     * 
     * Responses:
     *  - 200: Outfit session details.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @return [OutfitSession]
     */
    @GET("api/v1/outfits/{session_id}")
    suspend fun getOutfitSession(@Path("session_id") sessionId: java.util.UUID): Response<OutfitSession>

    /**
     * GET api/v1/outfits
     * List outfit sessions for the current owner
     * 
     * Responses:
     *  - 200: Outfit session page.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @return [OutfitSessionPage]
     */
    @GET("api/v1/outfits")
    suspend fun listOutfitSessions(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50): Response<OutfitSessionPage>

    /**
     * POST api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}/reapply
     * Reapply a pending layer, preferring the original Provider and parameters
     * Always creates a new traceable job. If the original Provider is unavailable or incompatible, an explicit compatible Provider must be supplied; otherwise the layer stays pending_reapply and no job is created.
     * Responses:
     *  - 201: Reapply job created and linked to the session.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The selected provider is disabled, unavailable, or capability-incompatible.
     *
     * @param sessionId 
     * @param branchId 
     * @param layerId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param reapplyOutfitLayerRequest 
     * @return [OutfitLayerResult]
     */
    @POST("api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}/reapply")
    suspend fun reapplyOutfitLayer(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID, @Path("layer_id") layerId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body reapplyOutfitLayerRequest: ReapplyOutfitLayerRequest): Response<OutfitLayerResult>

    /**
     * DELETE api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}
     * Remove or revert a layer and mark subsequent layers pending_reapply
     * 
     * Responses:
     *  - 200: Updated session; no automatic generation or fee.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param branchId 
     * @param layerId 
     * @param removeOutfitLayerRequest  (optional)
     * @return [OutfitSession]
     */
    @DELETE("api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}")
    suspend fun removeOutfitLayer(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID, @Path("layer_id") layerId: java.util.UUID, @Body removeOutfitLayerRequest: RemoveOutfitLayerRequest? = null): Response<OutfitSession>

    /**
     * POST api/v1/outfits/{session_id}/branches/{branch_id}/revisions/{revision_id}/select
     * Commit a new immutable revision from an explicit candidate selection
     * Only an explicit candidate selection commits a new confirmed revision. Failed, cancelled, or needs_attention attempts never change the current revision.
     * Responses:
     *  - 200: New confirmed revision committed; updated session returned.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: The command is not allowed from the current job or item state.
     *
     * @param sessionId 
     * @param branchId 
     * @param revisionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param selectOutfitRevisionRequest 
     * @return [OutfitSession]
     */
    @POST("api/v1/outfits/{session_id}/branches/{branch_id}/revisions/{revision_id}/select")
    suspend fun selectOutfitRevision(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID, @Path("revision_id") revisionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body selectOutfitRevisionRequest: SelectOutfitRevisionRequest): Response<OutfitSession>

    /**
     * POST api/v1/outfits/{session_id}/route
     * Switch split/dress route by creating a new branch from the original person image
     * Removes route-conflicting layers and keeps compatible outerwear as pending_reapply. The original branch is unchanged, and no generation task or fee is created by the switch.
     * Responses:
     *  - 200: New branch created for the target route; updated session returned.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param idempotencyKey Opaque client-generated key bound to the authenticated actor, operation, and canonical request payload. A successful replay returns the original stable result. Reusing a key with a different payload returns idempotency_key_reused. Streaming append is instead guarded by the server-confirmed Upload-Offset.
     * @param switchOutfitRouteRequest 
     * @return [OutfitSession]
     */
    @POST("api/v1/outfits/{session_id}/route")
    suspend fun switchOutfitRoute(@Path("session_id") sessionId: java.util.UUID, @Header("Idempotency-Key") idempotencyKey: kotlin.String, @Body switchOutfitRouteRequest: SwitchOutfitRouteRequest): Response<OutfitSession>

    /**
     * PATCH api/v1/outfits/{session_id}/branches/{branch_id}
     * Rename, favorite, or set a branch as the current mainline
     * Setting mainline moves the session mainline. A branch with unfinished tasks cannot be deleted, and the current mainline must be changed before it can be deleted.
     * Responses:
     *  - 200: Updated session.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param branchId 
     * @param updateOutfitBranchRequest 
     * @return [OutfitSession]
     */
    @PATCH("api/v1/outfits/{session_id}/branches/{branch_id}")
    suspend fun updateOutfitBranch(@Path("session_id") sessionId: java.util.UUID, @Path("branch_id") branchId: java.util.UUID, @Body updateOutfitBranchRequest: UpdateOutfitBranchRequest): Response<OutfitSession>

    /**
     * PATCH api/v1/outfits/{session_id}
     * Rename or favorite a session
     * 
     * Responses:
     *  - 200: Updated session.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param sessionId 
     * @param updateOutfitSessionRequest 
     * @return [OutfitSession]
     */
    @PATCH("api/v1/outfits/{session_id}")
    suspend fun updateOutfitSession(@Path("session_id") sessionId: java.util.UUID, @Body updateOutfitSessionRequest: UpdateOutfitSessionRequest): Response<OutfitSession>

}
