package com.clothesmodel.android.tryon

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

private val Context.tryOnDataStore by preferencesDataStore("try_on_draft")

data class TryOnDraft(
    val personImportId: String? = null,
    val garmentImportId: String? = null,
    val garmentCategory: String = "upper_body",
    val garmentSource: String = "custom",
    val activeJobId: String? = null,
    val createIdempotencyKey: String? = null,
)

class TryOnDraftStore(private val context: Context) {
    suspend fun snapshot(): TryOnDraft {
        val values = context.tryOnDataStore.data.first()
        return TryOnDraft(
            personImportId = values[PERSON_IMPORT],
            garmentImportId = values[GARMENT_IMPORT],
            garmentCategory = values[GARMENT_CATEGORY] ?: "upper_body",
            garmentSource = values[GARMENT_SOURCE] ?: "custom",
            activeJobId = values[ACTIVE_JOB],
            createIdempotencyKey = values[CREATE_KEY],
        )
    }

    suspend fun selectImport(kind: String, importId: String) {
        context.tryOnDataStore.edit { values ->
            values[if (kind == "person") PERSON_IMPORT else GARMENT_IMPORT] = importId
        }
    }

    suspend fun garmentMetadata(category: String, source: String = "custom") {
        context.tryOnDataStore.edit {
            it[GARMENT_CATEGORY] = category
            it[GARMENT_SOURCE] = source
        }
    }

    suspend fun rememberCreateKey(key: String) {
        context.tryOnDataStore.edit { it[CREATE_KEY] = key }
    }

    suspend fun activeJob(jobId: String) {
        context.tryOnDataStore.edit {
            it[ACTIVE_JOB] = jobId
            it.remove(CREATE_KEY)
        }
    }

    companion object {
        private val PERSON_IMPORT = stringPreferencesKey("person_import_id")
        private val GARMENT_IMPORT = stringPreferencesKey("garment_import_id")
        private val GARMENT_CATEGORY = stringPreferencesKey("garment_category")
        private val GARMENT_SOURCE = stringPreferencesKey("garment_source")
        private val ACTIVE_JOB = stringPreferencesKey("active_job_id")
        private val CREATE_KEY = stringPreferencesKey("create_idempotency_key")
    }
}
