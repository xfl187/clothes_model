package com.clothesmodel.android.assets

import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetReferenceModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import com.clothesmodel.android.imports.PendingImport
import com.clothesmodel.android.imports.PendingImportDatabase
import com.clothesmodel.android.tryon.TryOnDraftStore
import java.io.File
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AssetDetailUiState(
    val asset: AssetModel? = null,
    val references: List<AssetReferenceModel> = emptyList(),
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: ProblemModel? = null,
    val conflict: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
)

@HiltViewModel
class AssetDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    @param:ApplicationContext private val context: Context,
    private val assets: AssetRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val database = PendingImportDatabase.build(context)
    private val drafts = TryOnDraftStore(context)
    private val assetId: String = savedStateHandle.get<String>("assetId").orEmpty()
    private val mutableState = MutableStateFlow(AssetDetailUiState())
    val state: StateFlow<AssetDetailUiState> = mutableState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            val id = runCatching { UUID.fromString(assetId) }.getOrNull()
            if (id == null) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = ProblemModel("invalid_id", "素材不存在。", 404, false),
                )
                return@launch
            }
            val local = database.pendingImports().get(assetId)
            if (local != null) {
                val draft = drafts.snapshot()
                val referenced = draft.personAssetId == assetId || draft.garmentAssetId == assetId
                mutableState.value = mutableState.value.copy(
                    asset = local.toAssetModel(),
                    references = if (referenced) {
                        listOf(
                            AssetReferenceModel(
                                id = id,
                                assetId = id,
                                sourceKind = "draft",
                                sourceId = id,
                                label = "当前试穿草稿",
                                active = true,
                                createdAt = Instant.now().atOffset(ZoneOffset.UTC),
                            ),
                        )
                    } else emptyList(),
                    loading = false,
                )
                return@launch
            }
            when (val outcome = assets.get(id)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    asset = outcome.value,
                    loading = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
            loadReferences(id)
        }
    }

    private suspend fun loadReferences(id: UUID) {
        when (val outcome = assets.references(id)) {
            is Outcome.Success -> mutableState.value = mutableState.value.copy(
                references = outcome.value.items.filter { it.active },
            )

            is Outcome.Problem -> Unit
            Outcome.AuthenticationExpired ->
                mutableState.value = mutableState.value.copy(authenticationExpired = true)
        }
    }

    fun toggleFavorite() {
        val asset = mutableState.value.asset ?: return
        viewModelScope.launch {
            val local = database.pendingImports().get(asset.id.toString())
            if (local != null) {
                database.pendingImports().setFavorite(
                    local.id,
                    !local.favorite,
                    System.currentTimeMillis(),
                )
                mutableState.value = mutableState.value.copy(
                    asset = asset.copy(favorite = !asset.favorite),
                )
                return@launch
            }
            when (val outcome = assets.setFavorite(asset.id, !asset.favorite)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    asset = outcome.value,
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

    fun deleteContent() {
        val asset = mutableState.value.asset ?: return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(busy = true, conflict = null, error = null)
            val local = database.pendingImports().get(asset.id.toString())
            if (local != null) {
                if (mutableState.value.references.isNotEmpty()) {
                    mutableState.value = mutableState.value.copy(
                        busy = false,
                        conflict = ProblemModel(
                            "asset_referenced",
                            "素材仍被草稿使用，请先替换或移除。",
                            409,
                            false,
                            mutableState.value.references.size,
                        ),
                    )
                    return@launch
                }
                File(local.stagedPath).delete()
                database.pendingImports().delete(local.id)
                imageLoader.evict(asset.id)
                mutableState.value = mutableState.value.copy(
                    asset = asset.copy(contentAvailable = false, localPath = null),
                    busy = false,
                )
                return@launch
            }
            when (val outcome = assets.deleteContent(asset.id)) {
                is Outcome.Success -> {
                    imageLoader.evict(asset.id)
                    mutableState.value = mutableState.value.copy(
                        asset = outcome.value,
                        references = emptyList(),
                        busy = false,
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    conflict = if (outcome.problem.code == "asset_referenced") {
                        outcome.problem
                    } else {
                        null
                    },
                    error = if (outcome.problem.code == "asset_referenced") {
                        null
                    } else {
                        outcome.problem
                    },
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    busy = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    fun dismissConflict() {
        mutableState.value = mutableState.value.copy(conflict = null)
    }

    override fun onCleared() {
        database.close()
        super.onCleared()
    }
}

private fun PendingImport.toAssetModel(): AssetModel = AssetModel(
    id = UUID.fromString(id),
    kind = assetKind,
    favorite = favorite,
    lifecycle = com.clothesmodel.android.data.AssetLifecycle.ACTIVE,
    contentAvailable = File(stagedPath).isFile,
    width = 1,
    height = 1,
    createdAt = Instant.ofEpochMilli(updatedAt).atOffset(ZoneOffset.UTC),
    garmentCategory = garmentCategory?.let(com.clothesmodel.android.data.GarmentCategory::fromWire),
    garmentSource = garmentSource?.let(com.clothesmodel.android.data.GarmentSource::fromWire),
    qualityWarnings = emptyList(),
    backendAssetId = assetId?.let(UUID::fromString),
    localPath = stagedPath,
    syncState = state,
)
