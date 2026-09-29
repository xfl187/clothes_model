package com.clothesmodel.android.tryon

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
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
    val personAssetId: String? = null,
    val garmentAssetId: String? = null,
    val candidateCount: Int = 1,
    val providerId: String? = null,
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
            personAssetId = values[PERSON_ASSET],
            garmentAssetId = values[GARMENT_ASSET],
            candidateCount = values[CANDIDATE_COUNT] ?: 1,
            providerId = values[PROVIDER_ID],
        )
    }

    suspend fun selectImport(kind: String, importId: String) {
        context.tryOnDataStore.edit { values ->
            values[if (kind == "person") PERSON_IMPORT else GARMENT_IMPORT] = importId
        }
    }

    suspend fun clearImport(kind: String) {
        context.tryOnDataStore.edit { values ->
            values.remove(if (kind == "person") PERSON_IMPORT else GARMENT_IMPORT)
        }
    }

    suspend fun selectAsset(kind: String, assetId: String) {
        context.tryOnDataStore.edit { values ->
            values[if (kind == "person") PERSON_ASSET else GARMENT_ASSET] = assetId
        }
    }

    suspend fun clearAsset(kind: String) {
        context.tryOnDataStore.edit { values ->
            values.remove(if (kind == "person") PERSON_ASSET else GARMENT_ASSET)
        }
    }

    suspend fun garmentMetadata(category: String, source: String = "custom") {
        context.tryOnDataStore.edit {
            it[GARMENT_CATEGORY] = category
            it[GARMENT_SOURCE] = source
        }
    }

    suspend fun candidateCount(value: Int) {
        context.tryOnDataStore.edit { it[CANDIDATE_COUNT] = value }
    }

    suspend fun provider(value: String?) {
        context.tryOnDataStore.edit {
            if (value == null) it.remove(PROVIDER_ID) else it[PROVIDER_ID] = value
        }
    }

    suspend fun rememberCreateKey(key: String) {
        context.tryOnDataStore.edit { it[CREATE_KEY] = key }
    }

    suspend fun clearCreateKey() {
        context.tryOnDataStore.edit { it.remove(CREATE_KEY) }
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
        private val PERSON_ASSET = stringPreferencesKey("person_asset_id")
        private val GARMENT_ASSET = stringPreferencesKey("garment_asset_id")
        private val CANDIDATE_COUNT = intPreferencesKey("candidate_count")
        private val PROVIDER_ID = stringPreferencesKey("provider_id")
    }
}
