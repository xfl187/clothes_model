package com.clothesmodel.android.imports

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.AssetsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.AssetLocalCopyAcknowledgement
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID
import okhttp3.OkHttpClient
import okhttp3.Request

class LegacyAssetMigrationWorker(
    context: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val vault = TokenVault(applicationContext)
        val token = vault.read() ?: return Result.failure()
        val connection = ConnectionStore(applicationContext, vault).snapshot()
        val url = connection.serverUrl ?: return Result.failure()
        val serverId = connection.serverInstanceId ?: return Result.retry()
        val ownerId = connection.ownerScopeId ?: return Result.retry()
        val database = PendingImportDatabase.build(applicationContext)
        return try {
            val api = ApiClient(url, authName = "AppBearer", bearerToken = token)
                .createService(AssetsApi::class.java)
            for (kind in listOf("person", "garment")) {
                var cursor: String? = null
                do {
                    val response = api.listAssets(cursor = cursor, limit = 100, kind = AssetKind.decode(kind))
                    if (response.code() == 401) return Result.failure()
                    val page = response.body() ?: return Result.retry()
                    for (asset in page.items.filter { it.contentAvailable }) {
                        if (database.pendingImports().byServerAssetId(asset.id.toString()) != null) continue
                        val bytes = download(url, token, asset.id) ?: return Result.retry()
                        val checksum = MessageDigest.getInstance("SHA-256").digest(bytes)
                            .joinToString("") { "%02x".format(it) }
                        if (asset.contentSha256 != null &&
                            !asset.contentSha256.equals(checksum, ignoreCase = true)
                        ) return Result.retry()
                        val localId = UUID.randomUUID()
                        val directory = File(applicationContext.filesDir, "local-assets").apply { mkdirs() }
                        val temporary = File(directory, "$localId.tmp")
                        val target = File(directory, "$localId.image")
                        FileOutputStream(temporary).use { output ->
                            output.write(bytes)
                            output.fd.sync()
                        }
                        check(temporary.renameTo(target))
                        val row = PendingImport(
                            id = localId.toString(),
                            stagedPath = target.absolutePath,
                            displayName = if (kind == "person") "人物图片" else "服装图片",
                            contentType = asset.contentType,
                            assetKind = kind,
                            state = "ready",
                            assetId = asset.id.toString(),
                            garmentCategory = asset.garmentCategory?.value,
                            garmentSource = asset.garmentSource?.value,
                            sha256 = checksum,
                            sizeBytes = bytes.size.toLong(),
                            serverInstanceId = serverId,
                            ownerScopeId = ownerId,
                            updatedAt = System.currentTimeMillis(),
                        )
                        database.pendingImports().save(row)
                        val acknowledged = api.confirmAssetLocalCopy(
                            asset.id,
                            AssetLocalCopyAcknowledgement(localId, checksum),
                        )
                        if (!acknowledged.isSuccessful) return Result.retry()
                    }
                    cursor = page.nextCursor?.takeIf { page.hasMore && it.isNotBlank() }
                } while (cursor != null)
            }
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        } finally {
            database.close()
        }
    }

    private fun download(url: String, token: String, assetId: UUID): ByteArray? {
        val request = Request.Builder()
            .url("${url.trimEnd('/')}/api/v1/assets/$assetId/content")
            .header("Authorization", "Bearer $token")
            .build()
        return OkHttpClient().newCall(request).execute().use { response ->
            if (response.isSuccessful) response.body?.bytes() else null
        }
    }

    companion object {
        fun enqueue(context: Context, serverId: String, ownerId: String) {
            val request = OneTimeWorkRequestBuilder<LegacyAssetMigrationWorker>()
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build(),
                )
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                "legacy-asset-migration-$serverId-$ownerId",
                ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
