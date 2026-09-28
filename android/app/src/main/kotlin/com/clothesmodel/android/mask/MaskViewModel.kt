package com.clothesmodel.android.mask

import android.content.Context
import android.graphics.BitmapFactory
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.clothesmodel.android.data.ContentRepository
import com.clothesmodel.android.data.AuthenticatedImageLoader
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobRepository
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemModel
import com.clothesmodel.android.data.ProviderModel
import com.clothesmodel.android.data.ProviderRepository
import com.clothesmodel.android.create.maskCompatibleProviders
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

data class MaskEditorUiState(
    val document: MaskDocument = MaskDocument(),
    val activeTool: MaskTool = MaskTool.DRAW,
    val radius: Float = 0.08f,
    val showPreview: Boolean = true,
    val sourceAssetId: UUID? = null,
    val sourceWidth: Int = 0,
    val sourceHeight: Int = 0,
    val job: JobModel? = null,
    val providers: List<ProviderModel> = emptyList(),
    val selectedProviderId: UUID? = null,
    val providerNote: String? = null,
    val loading: Boolean = true,
    val error: ProblemModel? = null,
    val submitError: ProblemModel? = null,
    val submitting: Boolean = false,
    val authenticationExpired: Boolean = false,
) {
    val hasUnsavedEdits: Boolean get() = !document.isBlank

    val compatibleManualMaskProviders: List<ProviderModel>
        get() = maskCompatibleProviders(providers)

    val canSubmit: Boolean
        get() = !submitting && !document.isBlank && selectedProviderId != null
}

@HiltViewModel
class MaskViewModel @Inject constructor(
    @param:ApplicationContext private val context: Context,
    savedStateHandle: SavedStateHandle,
    private val jobs: JobRepository,
    private val providers: ProviderRepository,
    private val content: ContentRepository,
    private val uploader: MaskUploader,
    val imageLoader: AuthenticatedImageLoader,
) : ViewModel() {
    private val jobId: String = savedStateHandle.get<String>("jobId").orEmpty()
    private val sourceAssetIdArg: String = savedStateHandle.get<String>("candidateId").orEmpty()
    private val draftStore = MaskDraftStore(context)
    private val mutableState = MutableStateFlow(MaskEditorUiState())
    val state: StateFlow<MaskEditorUiState> = mutableState.asStateFlow()
    private var sourceBytes: ByteArray? = null

    init {
        load()
    }

    private fun load() {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(loading = true, error = null)
            val id = runCatching { UUID.fromString(jobId) }.getOrNull()
            if (id == null) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = ProblemModel("invalid_id", "任务不存在。", 404, false),
                )
                return@launch
            }
            when (val outcome = jobs.get(id)) {
                is Outcome.Success -> {
                    val job = outcome.value
                    val source = job.personAssetIds.firstOrNull()
                        ?: runCatching { UUID.fromString(sourceAssetIdArg) }.getOrNull()
                    mutableState.value = mutableState.value.copy(job = job, sourceAssetId = source)
                    val draft = draftStore.snapshot()
                    if (draft != null && draft.jobId == jobId && source != null) {
                        draftStore.loadDocumentText(jobId)?.let { text ->
                            mutableState.value = mutableState.value.copy(
                                document = decodeMaskDocument(text),
                            )
                        }
                        renderDraftPreview(draft)
                    }
                    loadProviders(job, draft)
                    loadSource(source)
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    private fun loadSource(source: UUID?) {
        if (source == null) {
            mutableState.value = mutableState.value.copy(loading = false)
            return
        }
        viewModelScope.launch {
            when (val outcome = content.download(source)) {
                is Outcome.Success -> {
                    sourceBytes = outcome.value
                    val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeByteArray(outcome.value, 0, outcome.value.size, options)
                    mutableState.value = mutableState.value.copy(
                        loading = false,
                        sourceWidth = options.outWidth.coerceAtLeast(1),
                        sourceHeight = options.outHeight.coerceAtLeast(1),
                    )
                }

                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    error = outcome.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    loading = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    private fun loadProviders(job: JobModel, draft: MaskDraft?) {
        viewModelScope.launch {
            when (val outcome = providers.available(limit = 50)) {
                is Outcome.Success -> {
                    val list = outcome.value.items
                    val savedProvider = draft?.providerId ?: job.lockedProviderId?.toString()
                    val locked = list.firstOrNull { it.id.toString() == job.lockedProviderId?.toString() }
                    val compatible = maskCompatibleProviders(list)
                    val chosen = compatible.firstOrNull { it.id.toString() == savedProvider }
                        ?: locked?.takeIf { it.supportsManualMask && it.selectable }
                    val needsManual = locked == null || !locked.supportsManualMask || !locked.selectable
                    mutableState.value = mutableState.value.copy(
                        providers = list,
                        selectedProviderId = chosen?.id,
                        providerNote = when {
                            needsManual && compatible.isEmpty() ->
                                "当前没有支持手动遮罩的 Provider，无法执行遮罩修正。"

                            needsManual ->
                                "原 Provider 不支持或暂不可用手动遮罩，请选择兼容 Provider 后再提交。"

                            else -> null
                        },
                    )
                }

                else -> Unit
            }
        }
    }

    private suspend fun renderDraftPreview(draft: MaskDraft) {
        val file = draftStore.maskFile(draft.jobId)
        if (!file.isFile) return
        val bytes = runCatching { file.readBytes() }.getOrNull() ?: return
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        mutableState.value = mutableState.value.copy(
            sourceWidth = options.outWidth.coerceAtLeast(1),
            sourceHeight = options.outHeight.coerceAtLeast(1),
        )
    }

    fun setTool(tool: MaskTool) {
        mutableState.value = mutableState.value.copy(activeTool = tool)
    }

    fun setRadius(radius: Float) {
        mutableState.value = mutableState.value.copy(radius = radius)
    }

    fun togglePreview() {
        mutableState.value = mutableState.value.copy(showPreview = !mutableState.value.showPreview)
    }

    fun startStroke(point: MaskPoint) {
        val current = mutableState.value
        mutableState.value = current.copy(
            document = current.document.startStroke(current.activeTool, current.radius, point),
        )
    }

    fun extendStroke(point: MaskPoint) {
        val current = mutableState.value
        mutableState.value = current.copy(document = current.document.extendStroke(point))
    }

    fun undo() {
        mutableState.value = mutableState.value.copy(document = mutableState.value.document.undo())
    }

    fun clear() {
        mutableState.value = mutableState.value.copy(document = mutableState.value.document.clear())
    }

    fun persistDraft() {
        val current = mutableState.value
        val source = current.sourceAssetId ?: return
        if (!current.hasUnsavedEdits || current.sourceWidth <= 1 || current.sourceHeight <= 1) return
        val bytes = renderMaskBytes(current)
        draftStore.saveMaskFile(jobId, bytes)
        draftStore.saveDocumentText(jobId, current.document.encode())
        viewModelScope.launch {
            draftStore.save(MaskDraft(jobId, source.toString(), current.selectedProviderId?.toString()))
        }
    }

    fun selectProvider(providerId: UUID) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(selectedProviderId = providerId, providerNote = null)
            val source = mutableState.value.sourceAssetId
            if (source != null) {
                draftStore.save(MaskDraft(jobId, source.toString(), providerId.toString()))
            }
        }
    }

    fun discard() {
        viewModelScope.launch { draftStore.clear() }
    }

    fun submit(onCreated: (String) -> Unit) {
        val current = mutableState.value
        val job = current.job ?: return
        val providerId = current.selectedProviderId ?: return
        if (current.document.isBlank) {
            mutableState.value = current.copy(
                submitError = ProblemModel("empty_mask", "请先绘制需要修正的遮罩区域。", 422, false),
            )
            return
        }
        viewModelScope.launch {
            mutableState.value = current.copy(submitting = true, submitError = null)
            val maskBytes = renderMaskBytes(current)
            when (val upload = uploader.upload(maskBytes)) {
                is Outcome.Success -> createJob(job, providerId, upload.value, onCreated)
                is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                    submitting = false,
                    submitError = upload.problem,
                )

                Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                    submitting = false,
                    authenticationExpired = true,
                )
            }
        }
    }

    private suspend fun createJob(
        job: JobModel,
        providerId: UUID,
        maskAssetId: UUID,
        onCreated: (String) -> Unit,
    ) {
        val garmentAssetId = job.garmentAssetId
        if (garmentAssetId == null || job.personAssetIds.isEmpty()) {
            mutableState.value = mutableState.value.copy(
                submitting = false,
                submitError = ProblemModel("invalid_job", "原任务输入不完整。", 422, false),
            )
            return
        }
        val request = CreateJobRequest(
            personAssetIds = job.personAssetIds,
            garmentAssetId = garmentAssetId,
            providerId = providerId,
            mode = TryOnMode.precise_try_on,
            generationOptions = GenerationOptions(candidateCount = job.candidateCount),
            maskAssetId = maskAssetId,
            relatedJobId = job.id,
        )
        when (val outcome = jobs.create(request, UUID.randomUUID().toString())) {
            is Outcome.Success -> {
                draftStore.clear()
                mutableState.value = mutableState.value.copy(submitting = false)
                onCreated(outcome.value.id.toString())
            }

            is Outcome.Problem -> mutableState.value = mutableState.value.copy(
                submitting = false,
                submitError = outcome.problem,
            )

            Outcome.AuthenticationExpired -> mutableState.value = mutableState.value.copy(
                submitting = false,
                authenticationExpired = true,
            )
        }
    }

    private fun renderMaskBytes(current: MaskEditorUiState): ByteArray =
        MaskRenderer.render(
            document = current.document,
            width = current.sourceWidth,
            height = current.sourceHeight,
        )
}
