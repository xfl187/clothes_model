package com.clothesmodel.android.mask

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.io.File
import kotlinx.coroutines.flow.first

private val Context.maskDataStore by preferencesDataStore("mask_draft")

data class MaskDraft(
    val jobId: String,
    val sourceAssetId: String,
    val providerId: String? = null,
)

class MaskDraftStore(context: Context) {
    private val appContext = context.applicationContext

    private val directory: File
        get() = File(appContext.filesDir, "mask-drafts").apply { mkdirs() }

    suspend fun snapshot(): MaskDraft? {
        val values = appContext.maskDataStore.data.first()
        val jobId = values[JOB_ID] ?: return null
        val sourceAssetId = values[SOURCE_ASSET_ID] ?: return null
        return MaskDraft(
            jobId = jobId,
            sourceAssetId = sourceAssetId,
            providerId = values[PROVIDER_ID],
        )
    }

    suspend fun save(draft: MaskDraft) {
        appContext.maskDataStore.edit {
            it[JOB_ID] = draft.jobId
            it[SOURCE_ASSET_ID] = draft.sourceAssetId
            if (draft.providerId == null) it.remove(PROVIDER_ID) else it[PROVIDER_ID] = draft.providerId
        }
    }

    fun saveMaskFile(jobId: String, bytes: ByteArray) {
        runCatching { maskFile(jobId).writeBytes(bytes) }
    }

    fun maskFile(jobId: String): File = File(directory, "$jobId.png")

    fun saveDocumentText(jobId: String, text: String) {
        runCatching { documentFile(jobId).writeText(text) }
    }

    fun loadDocumentText(jobId: String): String? =
        runCatching { documentFile(jobId).takeIf(File::isFile)?.readText() }.getOrNull()

    private fun documentFile(jobId: String): File = File(directory, "$jobId.mask.txt")

    suspend fun clear() {
        val draft = snapshot()
        appContext.maskDataStore.edit { it.clear() }
        draft?.let {
            runCatching { maskFile(it.jobId).delete() }
            runCatching { documentFile(it.jobId).delete() }
        }
    }

    companion object {
        private val JOB_ID = stringPreferencesKey("mask_job_id")
        private val SOURCE_ASSET_ID = stringPreferencesKey("mask_source_asset_id")
        private val PROVIDER_ID = stringPreferencesKey("mask_provider_id")
    }
}
