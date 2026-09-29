package com.clothesmodel.android.create

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.clothesmodel.android.data.AssetKindFilter
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.GarmentSource
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.data.ProviderRepository
import com.clothesmodel.android.imports.ImportStaging
import com.clothesmodel.android.imports.PendingImport
import com.clothesmodel.android.imports.PendingImportActions
import com.clothesmodel.android.imports.PendingImportDatabase
import com.clothesmodel.android.imports.PendingImportScheduler
import com.clothesmodel.android.imports.LocalAssetSyncResult
import com.clothesmodel.android.imports.LocalAssetUploader
import com.clothesmodel.android.tryon.TryOnDraftStore
import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.GenerationOptions
import com.clothesmodel.contract.model.TryOnMode
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import java.time.Instant
import java.time.ZoneOffset
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class WizardStep { PERSON, GARMENT, SETTINGS }

data class WizardImportUi(
    val id: String,
    val state: String,
    val error: String? = null,
) {
    val failed: Boolean
        get() = state == "failed" || error != null
}

data class CreateWizardUiState(
    val step: WizardStep = WizardStep.PERSON,
    val personAsset: AssetModel? = null,
    val garmentAsset: AssetModel? = null,
    val garmentCategory: GarmentCategory = GarmentCategory.UPPER_BODY,
    val assets: List<AssetModel> = emptyList(),
    val assetsLoading: Boolean = false,
    val assetError: ProblemModel? = null,
    val personImport: WizardImportUi? = null,
    val garmentImport: WizardImportUi? = null,
    val providers: List<ProviderModel> = emptyList(),
    val providerId: UUID? = null,
    val providerNote: String? = null,
    val candidateCount: Int = 1,
    val loading: Boolean = true,
    val submitting: Boolean = false,
    val createError: ProblemModel? = null,
    val authenticationExpired: Boolean = false,
) {
    val selectedProvider: ProviderModel?
        get() = providers.firstOrNull { it.id == providerId }

    val canAdvance: Boolean
        get() = when (step) {
            WizardStep.PERSON -> personAsset != null
            WizardStep.GARMENT -> garmentAsset != null
            WizardStep.SETTINGS -> selectedProvider != null
        }

    val currentImport: WizardImportUi?
        get() = when (step) {
            WizardStep.PERSON -> personImport
            WizardStep.GARMENT -> garmentImport
            WizardStep.SETTINGS -> null
        }

    val visibleAssets: List<AssetModel>
        get() = filterAssetsForStep(assets, step, garmentCategory)
}

internal fun filterAssetsForStep(
    assets: List<AssetModel>,
    step: WizardStep,
    garmentCategory: GarmentCategory,
): List<AssetModel> = if (step == WizardStep.GARMENT) {
    assets.filter { it.garmentCategory == garmentCategory }
} else {
    assets
}

@HiltViewModel
class CreateWizardViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
    private val assets: AssetRepository,
    private val jobs: JobRepository,
    private val providers: ProviderRepository,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val drafts = TryOnDraftStore(context)
    private val database = PendingImportDatabase.build(context)
    private val staging = ImportStaging(context)
    private val scheduler = PendingImportScheduler(context)
    private val uploader = LocalAssetUploader(context)
    private val importActions = PendingImportActions(context, database.pendingImports())
    private val mutableState = MutableStateFlow(CreateWizardUiState())
    val state: StateFlow<CreateWizardUiState> = mutableState.asStateFlow()

    init {
        observeImports()
        viewModelScope.launch {
            val draft = drafts.snapshot()
            mutableState.value = mutableState.value.copy(
                garmentCategory = GarmentCategory.fromWire(draft.garmentCategory),
                candidateCount = draft.candidateCount,
            )
            loadProviders(draft.providerId)
            restoreImport(draft.personImportId, WizardStep.PERSON)
            restoreImport(draft.garmentImportId, WizardStep.GARMENT)
            loadAssets(WizardStep.PERSON)
        }
    }

    fun goToStep(step: WizardStep) {
        mutableState.value = mutableState.value.copy(
            step = step,
            assets = if (step == WizardStep.SETTINGS) mutableState.value.assets else emptyList(),
            assetError = null,
        )
        if (step == WizardStep.PERSON || step == WizardStep.GARMENT) {
            loadAssets(step)
        }
    }

    fun next() {
        val current = mutableState.value
        if (!current.canAdvance) return
        val target = when (current.step) {
            WizardStep.PERSON -> WizardStep.GARMENT
            WizardStep.GARMENT -> WizardStep.SETTINGS
            WizardStep.SETTINGS -> WizardStep.SETTINGS
        }
        goToStep(target)
    }

    fun back() {
        val target = when (mutableState.value.step) {
            WizardStep.PERSON -> WizardStep.PERSON
            WizardStep.GARMENT -> WizardStep.PERSON
            WizardStep.SETTINGS -> WizardStep.GARMENT
        }
        goToStep(target)
    }

    fun selectPerson(asset: AssetModel) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(personAsset = asset)
            drafts.selectAsset("person", asset.id.toString())
        }
    }

    fun selectGarment(asset: AssetModel) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(garmentAsset = asset)
            drafts.selectAsset("garment", asset.id.toString())
        }
    }

    fun setGarmentCategory(category: GarmentCategory) {
        viewModelScope.launch {
            val selected = mutableState.value.garmentAsset
            val keepSelection = selected?.garmentCategory == category
            mutableState.value = mutableState.value.copy(
                garmentCategory = category,
                garmentAsset = selected?.takeIf { keepSelection },
            )
            if (selected != null && !keepSelection) drafts.clearAsset("garment")
            drafts.garmentMetadata(category.wire)
            reconcileProvider()
        }
    }

    fun import(uri: Uri) {
        val step = mutableState.value.step
        if (step != WizardStep.PERSON && step != WizardStep.GARMENT) return
        viewModelScope.launch {
            val id = runCatching {
                withContext(Dispatchers.IO) {
                    val staged = staging.copy(uri)
                    val id = UUID.randomUUID().toString()
                    val isGarment = step == WizardStep.GARMENT
                    database.pendingImports().save(
                        PendingImport(
                            id = id,
                            stagedPath = staged.file.absolutePath,
                            displayName = if (isGarment) "衣物图片" else "人物图片",
                            contentType = staged.contentType,
                            assetKind = step.wire,
                            garmentCategory = if (isGarment) {
                                mutableState.value.garmentCategory.wire
                            } else {
                                null
                            },
                            garmentSource = if (isGarment) GarmentSource.PHOTO.wire else null,
                            state = "staged",
                            sha256 = staged.sha256,
                            sizeBytes = staged.sizeBytes,
                            updatedAt = System.currentTimeMillis(),
                        ),
                    )
                    drafts.selectAsset(step.wire, id)
                    id
                }
            }.getOrElse {
                updateImport(
                    step,
                    WizardImportUi("", "failed", "无法保存所选图片，请重新选择。"),
                )
                return@launch
            }
            val pending = database.pendingImports().get(id) ?: return@launch
            val asset = pending.toAssetModel()
            mutableState.value = if (step == WizardStep.PERSON) {
                mutableState.value.copy(personAsset = asset)
            } else {
                mutableState.value.copy(garmentAsset = asset)
            }
            updateImport(step, null)
            loadAssets(step)
        }
    }

    fun retryImport(id: String) {
        if (id.isBlank()) return
        viewModelScope.launch {
            val pending = database.pendingImports().get(id) ?: return@launch
            database.pendingImports().save(
                pending.copy(state = "staged", lastError = null, updatedAt = System.currentTimeMillis()),
            )
            updateImport(pending.step, WizardImportUi(id, "staged"))
            scheduler.enqueue(id)
        }
    }

    fun cancelImport(id: String) {
        if (id.isBlank()) return
        viewModelScope.launch {
            val pending = database.pendingImports().get(id) ?: return@launch
            scheduler.cancel(id)
            if (importActions.cancel(id)) {
                drafts.clearImport(pending.step.wire)
                updateImport(pending.step, null)
            }
        }
    }

    fun selectProvider(provider: ProviderModel) {
        if (!provider.selectable) return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(
                providerId = provider.id,
                candidateCount = clampCandidateCount(mutableState.value.candidateCount, provider),
                providerNote = null,
            )
            drafts.provider(provider.id.toString())
            drafts.candidateCount(mutableState.value.candidateCount)
        }
    }

    fun setCandidateCount(count: Int) {
        val clamped = clampCandidateCount(count, mutableState.value.selectedProvider)
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(candidateCount = clamped)
            drafts.candidateCount(clamped)
        }
    }

    fun submit(onCreated: (String) -> Unit) {
        val current = mutableState.value
        val person = current.personAsset ?: return
        val garment = current.garmentAsset ?: return
        val provider = current.selectedProvider ?: return
        viewModelScope.launch {
            mutableState.value = current.copy(submitting = true, createError = null)
            val personSync = uploader.ensureUploaded(person.id.toString())
            val garmentSync = uploader.ensureUploaded(garment.id.toString())
            if (personSync !is LocalAssetSyncResult.Ready ||
                garmentSync !is LocalAssetSyncResult.Ready
            ) {
                val authenticationExpired = personSync is LocalAssetSyncResult.AuthenticationExpired ||
                    garmentSync is LocalAssetSyncResult.AuthenticationExpired
                val detail = listOf(personSync, garmentSync)
                    .filterIsInstance<LocalAssetSyncResult.Failed>()
                    .firstOrNull()?.detail ?: "需要重新认证后才能生成。"
                mutableState.value = mutableState.value.copy(
                    submitting = false,
                    authenticationExpired = authenticationExpired,
                    createError = ProblemModel("local_asset_sync_failed", detail, 0, true),
                )
                return@launch
            }
            val key = drafts.snapshot().createIdempotencyKey ?: UUID.randomUUID().toString().also {
                drafts.rememberCreateKey(it)
            }
            val request = CreateJobRequest(
                personAssetIds = listOf(personSync.backendAssetId),
                garmentAssetId = garmentSync.backendAssetId,
                providerId = provider.id,
                mode = TryOnMode.precise_try_on,
                generationOptions = GenerationOptions(candidateCount = current.candidateCount),
            )
            when (val outcome = jobs.create(request, key)) {
                is Outcome.Success -> {
                    drafts.clearCreateKey()
                    drafts.activeJob(outcome.value.id.toString())
                    mutableState.value = mutableState.value.copy(submitting = false)
                    onCreated(outcome.value.id.toString())
                }

                is Outcome.Problem -> {
                    if (outcome.problem.code != "network_unavailable") {
                        drafts.clearCreateKey()
                    }
                    mutableState.value = mutableState.value.copy(
                        submitting = false,
                        createError = outcome.problem,
                    )
                }

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    submitting = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    private fun loadAssets(step: WizardStep) {
        if (step == WizardStep.SETTINGS) return
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(assetsLoading = true, assetError = null)
            val kind = if (step == WizardStep.GARMENT) {
                AssetKindFilter.GARMENT
            } else {
                AssetKindFilter.PERSON
            }
            val connection = com.clothesmodel.android.connection.ConnectionStore(
                context,
                com.clothesmodel.android.connection.TokenVault(context),
            ).snapshot()
            val list = database.pendingImports()
                .byKindForOwner(kind.wire.orEmpty(), connection.serverInstanceId, connection.ownerScopeId)
                .filter { java.io.File(it.stagedPath).isFile }
                .map(PendingImport::toAssetModel)
            val draft = drafts.snapshot()
            val selectedId = if (step == WizardStep.PERSON) draft.personAssetId else draft.garmentAssetId
            val selected = list.firstOrNull { it.id.toString() == selectedId }
            mutableState.value = if (step == WizardStep.PERSON) {
                mutableState.value.copy(
                    assets = list,
                    personAsset = selected ?: mutableState.value.personAsset,
                    assetsLoading = false,
                )
            } else {
                mutableState.value.copy(
                    assets = list,
                    garmentAsset = selected ?: mutableState.value.garmentAsset,
                    assetsLoading = false,
                )
            }
        }
    }

    private fun observeImports() {
        viewModelScope.launch {
            WorkManager.getInstance(context)
                .getWorkInfosByTagFlow(PendingImportScheduler.AUTHENTICATED_UPLOAD_TAG)
                .map { work -> work.associate { it.id to it.state } }
                .distinctUntilChanged()
                .collect { reconcileImports() }
        }
    }

    private suspend fun reconcileImports() {
        val draft = drafts.snapshot()
        restoreImport(draft.personImportId, WizardStep.PERSON)
        restoreImport(draft.garmentImportId, WizardStep.GARMENT)
    }

    private suspend fun restoreImport(id: String?, step: WizardStep) {
        if (id == null) return
        val pending = database.pendingImports().get(id) ?: return
        if (java.io.File(pending.stagedPath).isFile) {
            val asset = pending.toAssetModel()
            if (step == WizardStep.PERSON) {
                mutableState.value = mutableState.value.copy(personAsset = asset)
            } else {
                mutableState.value = mutableState.value.copy(garmentAsset = asset)
            }
            drafts.selectAsset(step.wire, pending.id)
            drafts.clearImport(step.wire)
            updateImport(step, null)
            return
        }
        val work = withContext(Dispatchers.IO) {
            WorkManager.getInstance(context)
                .getWorkInfosByTag(PendingImportScheduler.importTag(id))
                .get()
        }
        val workFailed = work.isNotEmpty() && work.all { it.state.isFinished } &&
            work.none { it.state == WorkInfo.State.SUCCEEDED }
        val error = if (workFailed) {
            "上传失败，可重试或取消。"
        } else {
            pending.lastError
        }
        updateImport(step, WizardImportUi(id, pending.state, error))
    }

    private fun updateImport(step: WizardStep, value: WizardImportUi?) {
        mutableState.value = if (step == WizardStep.PERSON) {
            mutableState.value.copy(personImport = value)
        } else {
            mutableState.value.copy(garmentImport = value)
        }
    }

    private fun loadProviders(persistedProviderId: String?) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true)
            when (val outcome = providers.available(limit = 50)) {
                is Outcome.Success -> {
                    val list = outcome.value.items
                    val compatible = compatibleProviders(list, mutableState.value.garmentCategory)
                    val chosen = compatible.firstOrNull {
                        it.id.toString() == persistedProviderId
                    } ?: defaultProvider(compatible)
                    val note = if (persistedProviderId != null &&
                        compatible.none { it.id.toString() == persistedProviderId }
                    ) {
                        "原 Provider 不再兼容，请确认新的 Provider。"
                    } else {
                        null
                    }
                    mutableState.value = mutableState.value.copy(
                        providers = list,
                        providerId = chosen?.id,
                        candidateCount = clampCandidateCount(
                            mutableState.value.candidateCount,
                            chosen,
                        ),
                        providerNote = note,
                        loading = false,
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    assetError = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    providerNote = "后端未连接；可以继续选择本地素材，生成时再连接。",
                )
            }
        }
    }

    private suspend fun reconcileProvider() {
        val current = mutableState.value
        val compatible = compatibleProviders(current.providers, current.garmentCategory)
        if (current.providers.any { it.id == current.providerId } &&
            compatible.none { it.id == current.providerId }
        ) {
            val replacement = defaultProvider(compatible)
            mutableState.value = current.copy(
                providerId = replacement?.id,
                candidateCount = clampCandidateCount(current.candidateCount, replacement),
                providerNote = "该衣物类别下原 Provider 不兼容，已切换到可用的 Provider。",
            )
        }
    }

    override fun onCleared() {
        database.close()
        super.onCleared()
    }
}

private val WizardStep.wire: String
    get() = if (this == WizardStep.GARMENT) "garment" else "person"

private val PendingImport.step: WizardStep
    get() = if (assetKind == "garment") WizardStep.GARMENT else WizardStep.PERSON

private fun PendingImport.toAssetModel(): AssetModel = AssetModel(
    id = UUID.fromString(id),
    kind = assetKind,
    favorite = false,
    lifecycle = com.clothesmodel.android.data.AssetLifecycle.ACTIVE,
    contentAvailable = java.io.File(stagedPath).isFile,
    width = 1,
    height = 1,
    createdAt = Instant.ofEpochMilli(updatedAt).atOffset(ZoneOffset.UTC),
    garmentCategory = garmentCategory?.let(GarmentCategory::fromWire),
    garmentSource = garmentSource?.let(GarmentSource::fromWire),
    qualityWarnings = emptyList(),
    backendAssetId = assetId?.let(UUID::fromString),
    localPath = stagedPath,
    syncState = state,
)
