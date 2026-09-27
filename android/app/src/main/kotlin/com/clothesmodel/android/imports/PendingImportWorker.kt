package com.clothesmodel.android.imports

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.UploadsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.model.AssetKind
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

class PendingImportWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(IMPORT_ID) ?: return Result.failure()
        val database = PendingImportDatabase.build(applicationContext)
        return try {
            val pending = database.pendingImports().get(id) ?: return Result.success()
            if (!File(pending.stagedPath).isFile) return Result.failure()
            val vault = TokenVault(applicationContext)
            val token = vault.read()
            val connections = ConnectionStore(applicationContext, vault)
            val connection = connections.snapshot()
            if (token == null || connection.serverUrl == null) {
                connections.authenticationExpired()
                Result.failure()
            } else {
                val serverUrl = connection.serverUrl
                val api = ApiClient(serverUrl, authName = "AppBearer", bearerToken = token).createService(UploadsApi::class.java)
                val source = File(pending.stagedPath)
                val upload = if (pending.uploadId == null) {
                    val response = api.createUploadSession(
                        "create-${pending.id}",
                        UploadCreateRequest(
                            assetKind = AssetKind.decode(pending.assetKind) ?: AssetKind.unknown,
                            filename = pending.displayName,
                            contentType = pending.contentType,
                            sizeBytes = source.length(),
                            garmentCategory = pending.garmentCategory?.let { GarmentCategory.decode(it) },
                            garmentSource = pending.garmentSource?.let { GarmentSource.decode(it) },
                        ),
                    )
                    if (response.code() == 401) return authenticationExpired(connections)
                    response.body() ?: return Result.retry()
                } else {
                    val response = api.getUploadSession(UUID.fromString(pending.uploadId))
                    if (response.code() == 401) return authenticationExpired(connections)
                    response.body() ?: return Result.retry()
                }
                database.pendingImports().save(pending.copy(uploadId = upload.id.toString(), confirmedOffset = upload.uploadedBytes, state = "uploading"))
                if (upload.uploadedBytes < source.length()) {
                    val chunk = File.createTempFile("upload-", ".chunk", applicationContext.cacheDir)
                    try {
                        source.inputStream().use { input ->
                            var remaining = upload.uploadedBytes
                            while (remaining > 0) {
                                val skipped = input.skip(remaining)
                                if (skipped <= 0) return Result.retry()
                                remaining -= skipped
                            }
                            chunk.outputStream().use(input::copyTo)
                        }
                        // The generated client cannot create a raw request body from a File,
                        // so the streaming append is sent directly as octet-stream bytes.
                        val status = appendChunk(serverUrl, token, upload.id.toString(), upload.uploadedBytes, chunk)
                        if (status == 401) return authenticationExpired(connections)
                        if (status !in 200..299) return Result.retry()
                    } finally { chunk.delete() }
                }
                val checksum = source.inputStream().use { input -> MessageDigest.getInstance("SHA-256").digest(input.readBytes()).joinToString("") { "%02x".format(it) } }
                val completed = api.completeUploadSession(upload.id, "complete-${pending.id}", UploadCompleteRequest(checksum))
                if (completed.code() == 401) return authenticationExpired(connections)
                val asset = completed.body() ?: return Result.retry()
                database.pendingImports().save(pending.copy(uploadId = upload.id.toString(), confirmedOffset = source.length(), state = "completed", assetId = asset.id.toString()))
                source.delete()
                Result.success()
            }
        } finally {
            database.close()
        }
    }

    private fun appendChunk(
        serverUrl: String,
        token: String,
        uploadId: String,
        offset: Long,
        chunk: File,
    ): Int {
        val request = Request.Builder()
            .url("${serverUrl.trimEnd('/')}/api/v1/uploads/$uploadId/content")
            .patch(chunk.asRequestBody("application/offset+octet-stream".toMediaType()))
            .header("Authorization", "Bearer $token")
            .header("Upload-Offset", offset.toString())
            .build()
        OkHttpClient().newCall(request).execute().use { return it.code }
    }

    private suspend fun authenticationExpired(connections: ConnectionStore): Result {
        connections.authenticationExpired()
        WorkManager.getInstance(applicationContext).cancelAllWorkByTag(
            PendingImportScheduler.AUTHENTICATED_UPLOAD_TAG,
        )
        return Result.failure()
    }

    companion object { const val IMPORT_ID = "import_id" }
}
