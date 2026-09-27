package com.clothesmodel.android.imports

import android.content.Context
import com.clothesmodel.android.connection.ConnectionStore
import com.clothesmodel.android.connection.TokenVault
import com.clothesmodel.contract.api.UploadsApi
import com.clothesmodel.contract.infrastructure.ApiClient
import java.io.File
import java.util.UUID

class PendingImportActions(
    private val context: Context,
    private val dao: PendingImportDao,
) {
    suspend fun cancel(importId: String): Boolean {
        val pending = dao.get(importId) ?: return true
        val vault = TokenVault(context)
        val token = vault.read() ?: return false
        val connection = ConnectionStore(context, vault).snapshot()
        val uploadId = pending.uploadId
        if (uploadId != null) {
            val api = ApiClient(
                connection.serverUrl ?: return false,
                authName = "AppBearer",
                bearerToken = token,
            ).createService(UploadsApi::class.java)
            val response = api.cancelUploadSession(UUID.fromString(uploadId))
            if (response.code() == 401) {
                ConnectionStore(context, vault).authenticationExpired()
                return false
            }
            if (!response.isSuccessful) return false
        }
        File(pending.stagedPath).delete()
        dao.delete(importId)
        return true
    }
}
