package com.clothesmodel.android.imports

import android.content.Context
import androidx.room.Room
import androidx.work.CoroutineWorker
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.UploadsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.UploadCompleteRequest
import com.clothesmodel.contract.model.UploadCreateRequest
import java.io.File
import java.security.MessageDigest
import java.util.UUID

class PendingImportWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(IMPORT_ID) ?: return Result.failure()
        val database = Room.databaseBuilder(applicationContext, PendingImportDatabase::class.java, "pending-imports.db").build()
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
                val api = ApiClient(connection.serverUrl, authName = "AppBearer", bearerToken = token).createService(UploadsApi::class.java)
                val source = File(pending.stagedPath)
                val upload = if (pending.uploadId == null) {
                    val response = api.createUploadSession(
                        "create-${pending.id}",
                        UploadCreateRequest(AssetKind.decode(pending.assetKind) ?: AssetKind.unknown, pending.displayName, pending.contentType, source.length()),
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
                        val appended = api.appendUploadContent(upload.id, upload.uploadedBytes, chunk)
                        if (appended.code() == 401) return authenticationExpired(connections)
                        if (!appended.isSuccessful) return Result.retry()
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

    private suspend fun authenticationExpired(connections: ConnectionStore): Result {
        connections.authenticationExpired()
        WorkManager.getInstance(applicationContext).cancelAllWorkByTag(
            PendingImportScheduler.AUTHENTICATED_UPLOAD_TAG,
        )
        return Result.failure()
    }

    companion object { const val IMPORT_ID = "import_id" }
}
