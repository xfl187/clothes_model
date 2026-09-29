package com.clothesmodel.android.imports

import android.content.Context
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.AssetsApi
import com.clothesmodel.contract.api.UploadsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.AssetLocalCopyAcknowledgement
import com.clothesmodel.contract.model.GarmentCategory
import com.clothesmodel.contract.model.GarmentSource
import com.clothesmodel.contract.model.UploadCompleteRequest
import com.clothesmodel.contract.model.UploadCreateRequest
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody

sealed interface LocalAssetSyncResult {
    data class Ready(val backendAssetId: UUID) : LocalAssetSyncResult
    data object AuthenticationExpired : LocalAssetSyncResult
    data class Failed(val detail: String) : LocalAssetSyncResult
}

class LocalAssetUploader(private val context: Context) {
    suspend fun ensureUploaded(localId: String): LocalAssetSyncResult {
        val database = PendingImportDatabase.build(context)
        try {
            val dao = database.pendingImports()
            var local = dao.get(localId) ?: return LocalAssetSyncResult.Failed("本地素材不存在。")
            val source = File(local.stagedPath)
            if (!source.isFile) return LocalAssetSyncResult.Failed("本地原图缺失，请重新选择。")
            val vault = TokenVault(context)
            val token = vault.read() ?: return LocalAssetSyncResult.AuthenticationExpired
            val connection = ConnectionStore(context, vault).snapshot()
            val serverUrl = connection.serverUrl ?: return LocalAssetSyncResult.Failed("尚未连接后端。")
            if (local.serverInstanceId != null && local.serverInstanceId != connection.serverInstanceId) {
                return LocalAssetSyncResult.Failed("素材属于另一台后端，无法上传。")
            }
            if (local.ownerScopeId != null && local.ownerScopeId != connection.ownerScopeId) {
                return LocalAssetSyncResult.Failed("素材属于另一账号，无法上传。")
            }
            val client = ApiClient(serverUrl, authName = "AppBearer", bearerToken = token)
            val assets = client.createService(AssetsApi::class.java)
            val uploads = client.createService(UploadsApi::class.java)
            val existingId = local.assetId?.let(UUID::fromString)
            if (existingId != null) {
                val existing = assets.getAsset(existingId)
                if (existing.code() == 401) return LocalAssetSyncResult.AuthenticationExpired
                if (existing.isSuccessful && existing.body()?.contentAvailable == true) {
                    acknowledge(assets, existingId, local)
                    return LocalAssetSyncResult.Ready(existingId)
                }
            }
            val checksum = local.sha256 ?: sha256(source)
            local = local.copy(
                state = "uploading",
                sha256 = checksum,
                sizeBytes = source.length(),
                serverInstanceId = connection.serverInstanceId,
                ownerScopeId = connection.ownerScopeId,
                updatedAt = System.currentTimeMillis(),
            )
            dao.save(local)
            val created = uploads.createUploadSession(
                "create-${local.id}",
                UploadCreateRequest(
                    assetKind = AssetKind.decode(local.assetKind) ?: AssetKind.unknown,
                    filename = local.displayName,
                    contentType = local.contentType,
                    sizeBytes = source.length(),
                    garmentCategory = local.garmentCategory?.let(GarmentCategory::decode),
                    garmentSource = local.garmentSource?.let(GarmentSource::decode),
                    targetAssetId = existingId,
                ),
            )
            if (created.code() == 401) return LocalAssetSyncResult.AuthenticationExpired
            val upload = created.body() ?: return LocalAssetSyncResult.Failed("无法创建上传任务。")
            dao.save(local.copy(uploadId = upload.id.toString(), confirmedOffset = upload.uploadedBytes))
            if (upload.uploadedBytes < source.length()) {
                val status = append(serverUrl, token, upload.id.toString(), upload.uploadedBytes, source)
                if (status == 401) return LocalAssetSyncResult.AuthenticationExpired
                if (status !in 200..299) return LocalAssetSyncResult.Failed("上传素材失败。")
            }
            val completed = uploads.completeUploadSession(
                upload.id,
                "complete-${local.id}",
                UploadCompleteRequest(checksum),
            )
            if (completed.code() == 401) return LocalAssetSyncResult.AuthenticationExpired
            val backend = completed.body() ?: return LocalAssetSyncResult.Failed("素材校验失败。")
            acknowledge(assets, backend.id, local.copy(sha256 = checksum))
            dao.save(
                local.copy(
                    uploadId = upload.id.toString(),
                    confirmedOffset = source.length(),
                    state = "ready",
                    assetId = backend.id.toString(),
                    sha256 = checksum,
                    lastError = null,
                    updatedAt = System.currentTimeMillis(),
                ),
            )
            return LocalAssetSyncResult.Ready(backend.id)
        } catch (error: Exception) {
            return LocalAssetSyncResult.Failed(error.message ?: "素材同步失败。")
        } finally {
            database.close()
        }
    }

    private suspend fun acknowledge(api: AssetsApi, assetId: UUID, local: PendingImport) {
        val checksum = local.sha256 ?: return
        api.confirmAssetLocalCopy(
            assetId,
            AssetLocalCopyAcknowledgement(UUID.fromString(local.id), checksum),
        )
    }

    private fun append(url: String, token: String, uploadId: String, offset: Long, source: File): Int {
        val chunk = File.createTempFile("upload-", ".chunk", context.cacheDir)
        return try {
            source.inputStream().use { input ->
                var remaining = offset
                while (remaining > 0) remaining -= input.skip(remaining)
                chunk.outputStream().use(input::copyTo)
            }
            val request = Request.Builder()
                .url("${url.trimEnd('/')}/api/v1/uploads/$uploadId/content")
                .patch(chunk.asRequestBody("application/offset+octet-stream".toMediaType()))
                .header("Authorization", "Bearer $token")
                .header("Upload-Offset", offset.toString())
                .build()
            OkHttpClient().newCall(request).execute().use { it.code }
        } finally {
            chunk.delete()
        }
    }

    private fun sha256(file: File): String = file.inputStream().use { input ->
        MessageDigest.getInstance("SHA-256").digest(input.readBytes())
            .joinToString("") { "%02x".format(it) }
    }
}
