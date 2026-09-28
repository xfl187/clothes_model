package com.clothesmodel.android.assets

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetKindFilter
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.GarmentSource
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.imports.ImportStaging
import com.clothesmodel.android.imports.PendingImport
import com.clothesmodel.android.imports.PendingImportActions
import com.clothesmodel.android.imports.PendingImportDatabase
import com.clothesmodel.android.imports.PendingImportScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class AssetSegment(val wire: String, val label: String) {
    PERSON("person", "人物"),
    GARMENT("garment", "衣物"),
}

data class PendingImportUi(
    val id: String,
    val displayName: String,
    val state: String,
    val uploadedBytes: Long,
    val totalBytes: Long,
    val error: String?,
    val assetId: String?,
) {
    val inProgress: Boolean
        get() = state != "completed" && state != "failed"

    val failed: Boolean
        get() = state == "failed" || error != null
}

data class AssetCenterUiState(
    val segment: AssetSegment = AssetSegment.PERSON,
    val categoryFilter: GarmentCategory? = null,
    val assets: List<AssetModel> = emptyList(),
    val imports: List<PendingImportUi> = emptyList(),
    val nextCursor: String? = null,
    val hasMore: Boolean = false,
    val loading: Boolean = true,
    val loadingMore: Boolean = false,
    val error: ProblemModel? = null,
    val stale: Boolean = false,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class AssetCenterViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
    private val assets: AssetRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val database = PendingImportDatabase.build(context)
    private val staging = ImportStaging(context)
    private val scheduler = PendingImportScheduler(context)
    private val actions = PendingImportActions(context, database.pendingImports())
    private val mutableState = MutableStateFlow(AssetCenterUiState())
    val state: StateFlow<AssetCenterUiState> = mutableState.asStateFlow()

    init {
        refresh()
    }

    fun selectSegment(segment: AssetSegment) {
        if (segment == mutableState.value.segment) return
        mutableState.value = mutableState.value.copy(
            segment = segment,
            categoryFilter = null,
            assets = emptyList(),
            nextCursor = null,
            hasMore = false,
            loading = true,
            error = null,
        )
        refresh()
    }

    fun setCategoryFilter(category: GarmentCategory?) {
        mutableState.value = mutableState.value.copy(categoryFilter = category)
    }

    fun refresh() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            loadImports()
            when (val outcome = assets.list(kind = mutableState.value.segment.toFilter(), limit = 50)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    assets = outcome.value.items,
                    nextCursor = outcome.value.nextCursor,
                    hasMore = outcome.value.hasMore,
                    loading = false,
                    stale = false,
                    error = null,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    stale = mutableState.value.assets.isNotEmpty(),
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun loadMore() {
        val current = mutableState.value
        val cursor = current.nextCursor ?: return
        if (current.loadingMore || !current.hasMore) return
        viewModelScope.launch {
            mutableState.value = current.copy(loadingMore = true)
            when (val outcome = assets.list(kind = current.segment.toFilter(), cursor = cursor)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    assets = mutableState.value.assets + outcome.value.items,
                    nextCursor = outcome.value.nextCursor,
                    hasMore = outcome.value.hasMore,
                    loadingMore = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loadingMore = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loadingMore = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun toggleFavorite(asset: AssetModel) {
        viewModelScope.launch {
            when (val outcome = assets.setFavorite(asset.id, !asset.favorite)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    assets = mutableState.value.assets.map {
                        if (it.id == asset.id) outcome.value else it
                    },
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    authenticationExpired = true,
                )
            }
        }
    }

    fun import(
        uri: Uri,
        category: GarmentCategory = GarmentCategory.UPPER_BODY,
        source: GarmentSource = GarmentSource.PHOTO,
    ) {
        viewModelScope.launch {
            val segment = mutableState.value.segment
            runCatching {
                withContext(Dispatchers.IO) {
                    val staged = staging.copy(uri)
                    val id = UUID.randomUUID().toString()
                    val isGarment = segment == AssetSegment.GARMENT
                    database.pendingImports().save(
                        PendingImport(
                            id = id,
                            stagedPath = staged.file.absolutePath,
                            displayName = if (isGarment) "服装图片" else "人物图片",
                            contentType = staged.contentType,
                            assetKind = segment.wire,
                            garmentCategory = if (isGarment) category.wire else null,
                            garmentSource = if (isGarment) source.wire else null,
                            state = "staged",
                            updatedAt = System.currentTimeMillis(),
                        ),
                    )
                    scheduler.enqueue(id)
                }
            }.onSuccess {
                loadImports()
            }.onFailure {
                mutableState.value = mutableState.value.copy(
                    error = ProblemModel("import_stage_failed", "无法保存所选图片。", 0, true),
                )
            }
        }
    }

    fun retryImport(id: String) {
        viewModelScope.launch {
            database.pendingImports().get(id)?.let {
                database.pendingImports().save(
                    it.copy(state = "staged", lastError = null, updatedAt = System.currentTimeMillis()),
                )
                scheduler.enqueue(id)
                loadImports()
            }
        }
    }

    fun cancelImport(id: String) {
        viewModelScope.launch {
            scheduler.cancel(id)
            actions.cancel(id)
            loadImports()
        }
    }

    private suspend fun loadImports() {
        val kind = mutableState.value.segment.wire
        val rows = database.pendingImports().byKind(kind)
        mutableState.value = mutableState.value.copy(
            imports = rows
                .filter { it.state != "completed" }
                .map { it.toUi() },
        )
    }

    private fun PendingImport.toUi(): PendingImportUi {
        val total = runCatching { File(stagedPath).length() }.getOrDefault(0L)
        return PendingImportUi(
            id = id,
            displayName = displayName,
            state = state,
            uploadedBytes = confirmedOffset,
            totalBytes = total,
            error = lastError,
            assetId = assetId,
        )
    }

    override fun onCleared() {
        database.close()
        super.onCleared()
    }
}

private fun AssetSegment.toFilter(): AssetKindFilter = when (this) {
    AssetSegment.PERSON -> AssetKindFilter.PERSON
    AssetSegment.GARMENT -> AssetKindFilter.GARMENT
}
