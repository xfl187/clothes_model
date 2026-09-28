package com.clothesmodel.android.create

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.AssetKindFilter
import com.clothesmodel.android.data.AssetModel
import com.clothesmodel.android.data.AssetRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.GarmentCategory
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.data.ProviderRepository
import com.clothesmodel.android.tryon.TryOnDraftStore
import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.GenerationOptions
import com.clothesmodel.contract.model.TryOnMode
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class WizardStep { PERSON, GARMENT, SETTINGS }

data class CreateWizardUiState(
    val step: WizardStep = WizardStep.PERSON,
    val personAsset: AssetModel? = null,
    val garmentAsset: AssetModel? = null,
    val garmentCategory: GarmentCategory = GarmentCategory.UPPER_BODY,
    val assets: List<AssetModel> = emptyList(),
    val assetsLoading: Boolean = false,
    val assetError: ProblemModel? = null,
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
    private val mutableState = MutableStateFlow(CreateWizardUiState())
    val state: StateFlow<CreateWizardUiState> = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            val draft = drafts.snapshot()
            mutableState.value = mutableState.value.copy(
                garmentCategory = GarmentCategory.fromWire(draft.garmentCategory),
                candidateCount = draft.candidateCount,
            )
            loadProviders(draft.providerId)
            loadAssets()
        }
    }

    fun goToStep(step: WizardStep) {
        mutableState.value = mutableState.value.copy(step = step)
        if ((step == WizardStep.PERSON || step == WizardStep.GARMENT) &&
            mutableState.value.assets.isEmpty()
        ) {
            loadAssets()
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
            mutableState.value = mutableState.value.copy(garmentCategory = category)
            drafts.garmentMetadata(category.wire)
            reconcileProvider()
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
            val key = drafts.snapshot().createIdempotencyKey ?: UUID.randomUUID().toString().also {
                drafts.rememberCreateKey(it)
            }
            val request = CreateJobRequest(
                personAssetIds = listOf(person.id),
                garmentAssetId = garment.id,
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

    private fun loadAssets() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(assetsLoading = true, assetError = null)
            val kind = if (mutableState.value.step == WizardStep.GARMENT) {
                AssetKindFilter.GARMENT
            } else {
                AssetKindFilter.PERSON
            }
            when (val outcome = assets.list(kind = kind, limit = 50)) {
                is Outcome.Success -> mutableState.value = mutableState.value.copy(
                    assets = outcome.value.items.filter { it.contentAvailable },
                    assetsLoading = false,
                )

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    assetsLoading = false,
                    assetError = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    assetsLoading = false,
                    authenticationExpired = true,
                )
            }
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
                    authenticationExpired = true,
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
}
