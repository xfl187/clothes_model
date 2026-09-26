package com.clothesmodel.contract.api

import com.clothesmodel.contract.infrastructure.CollectionFormats.*
import retrofit2.http.*
import retrofit2.Response
import okhttp3.RequestBody
import okhttp3.ResponseBody
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

import com.clothesmodel.contract.model.Asset
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.AssetPage
import com.clothesmodel.contract.model.ProblemDetails

interface AssetsApi {
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
     * GET api/v1/assets
     * List reusable person, garment, result, or mask assets
     * 
     * Responses:
     *  - 200: Asset page ordered by created_at and id.
     *  - 401: Authentication is missing or invalid.
     *
     * @param cursor Opaque cursor returned by the previous page. (optional)
     * @param limit  (optional, default to 50)
     * @param kind  (optional)
     * @return [AssetPage]
     */
    @GET("api/v1/assets")
    suspend fun listAssets(@Query("cursor") cursor: kotlin.String? = null, @Query("limit") limit: kotlin.Int? = 50, @Query("kind") kind: AssetKind? = null): Response<AssetPage>

}
