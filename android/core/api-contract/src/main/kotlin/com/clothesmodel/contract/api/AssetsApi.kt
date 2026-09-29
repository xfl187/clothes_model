package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import okhttp3.ResponseBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.Asset
import com.clothesmodel.contract.model.AssetContentDeletionResult
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.AssetLocalCopyAcknowledgement
import com.clothesmodel.contract.model.AssetPage
import com.clothesmodel.contract.model.AssetReferencePage
import com.clothesmodel.contract.model.AssetUpdateRequest
import com.clothesmodel.contract.model.ProblemDetails

interface AssetsApi {
    /**
     * PUT api/v1/assets/{asset_id}/local-copy
     * Confirm a durable full Android copy of an owned person or garment
     * Safe to repeat with the same client material identifier and digest. The acknowledgement permits later reference-aware input-content cleanup but does not itself delete content or start a grace period.
     * Responses:
     *  - 200: Durable local copy acknowledged; current asset state returned.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Request failed with a stable machine-readable error code.
     *  - 422: Request failed with a stable machine-readable error code.
     *
     * @param assetId 
     * @param assetLocalCopyAcknowledgement 
     * @return [Asset]
     */
    @PUT("api/v1/assets/{asset_id}/local-copy")
    suspend fun confirmAssetLocalCopy(@Path("asset_id") assetId: java.util.UUID, @Body assetLocalCopyAcknowledgement: AssetLocalCopyAcknowledgement): Response<Asset>

    /**
     * DELETE api/v1/assets/{asset_id}/content
     * Remove private asset content while retaining a metadata placeholder
     * The operation is safe to repeat. Active references block deletion and can be inspected through the asset references resource.
     * Responses:
     *  - 200: Content was deleted or was already absent.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 409: Asset content cannot be deleted while active references exist.
     *
     * @param assetId 
     * @return [AssetContentDeletionResult]
     */
    @DELETE("api/v1/assets/{asset_id}/content")
    suspend fun deleteAssetContent(@Path("asset_id") assetId: java.util.UUID): Response<AssetContentDeletionResult>

    /**
     * GET api/v1/assets/{asset_id}/content
     * Download private asset content through an authenticated endpoint
     * 
     * Responses:
     *  - 200: Private image bytes.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param assetId 
     * @return [ResponseBody]
     */
    @GET("api/v1/assets/{asset_id}/content")
    suspend fun downloadAssetContent(@Path("asset_id") assetId: java.util.UUID): Response<ResponseBody>

    /**
     * GET api/v1/assets/{asset_id}
     * Read asset metadata, including deleted-content placeholders
     * 
     * Responses:
     *  - 200: Asset metadata.
     *  - 401: Authentication is missing or invalid.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param assetId 
     * @return [Asset]
     */
    @GET("api/v1/assets/{asset_id}")
    suspend fun getAsset(@Path("asset_id") assetId: java.util.UUID): Response<Asset>

    /**
     * GET api/v1/assets/{asset_id}/references
     * List active reference blockers for an asset
     * Results use the shared opaque cursor convention. Source identifiers are resource identifiers, never filesystem paths or content hashes.
     * Responses:
     *  - 200: Active reference page in deterministic creation order.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *  - 404: Request failed with a stable machine-readable error code.
     *
     * @param assetId 
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @return [AssetReferencePage]
     */
    @GET("api/v1/assets/{asset_id}/references")
    suspend fun listAssetReferences(@Path("asset_id") assetId: java.util.UUID, @Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50): Response<AssetReferencePage>

    /**
     * GET api/v1/assets
     * List reusable person, garment, result, or mask assets
     * 
     * Responses:
     *  - 200: Asset page ordered by created_at and id.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @param kind  (optional)
     * @return [AssetPage]
     */
    @GET("api/v1/assets")
    suspend fun listAssets(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50, @Query("kind") kind: AssetKind? = null): Response<AssetPage>

    /**
     * PATCH api/v1/assets/{asset_id}
     * Update mutable asset metadata
     * V1 Phase 2 permits only favorite-state changes.
     * Responses:
     *  - 200: Updated asset metadata.
     *  - 401: Authentication is missing or invalid.
     *  - 403: The authenticated principal does not have the required scope.
     *  - 404: Request failed with a stable machine-readable error code.
     *  - 422: Request failed with a stable machine-readable error code.
     *
     * @param assetId 
     * @param assetUpdateRequest 
     * @return [Asset]
     */
    @PATCH("api/v1/assets/{asset_id}")
    suspend fun updateAsset(@Path("asset_id") assetId: java.util.UUID, @Body assetUpdateRequest: AssetUpdateRequest): Response<Asset>

}
