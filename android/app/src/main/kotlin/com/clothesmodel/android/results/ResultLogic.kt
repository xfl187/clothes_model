package com.clothesmodel.android.results

import com.clothesmodel.android.data.CandidateModel
import com.clothesmodel.android.data.CandidateStateDomain
import com.clothesmodel.android.data.JobModel
import com.clothesmodel.android.data.JobOutputModel
import java.util.UUID

data class GalleryItem(
    val candidateIndex: Int,
    val attempt: Int,
    val output: JobOutputModel,
)

fun galleryItems(job: JobModel): List<GalleryItem> =
    job.candidates
        .flatMap { candidate ->
            candidate.outputs.map { output ->
                GalleryItem(
                    candidateIndex = candidate.candidateIndex,
                    attempt = candidate.attempt,
                    output = output,
                )
            }
        }
        .sortedWith(compareBy({ it.candidateIndex }, { it.attempt }))

fun traceableCandidates(job: JobModel): List<CandidateModel> =
    job.candidates.filter { candidate ->
        candidate.state == CandidateStateDomain.FAILED ||
            candidate.state == CandidateStateDomain.CANCELLED ||
            (candidate.state == CandidateStateDomain.NEEDS_ATTENTION && candidate.outputs.isEmpty())
    }

fun firstAvailableOutputAssetId(job: JobModel): UUID? =
    galleryItems(job).firstOrNull { it.output.contentAvailable }?.output?.assetId

fun updateOutput(
    job: JobModel,
    assetId: UUID,
    transform: (JobOutputModel) -> JobOutputModel,
): JobModel = job.copy(
    candidates = job.candidates.map { candidate ->
        if (candidate.outputs.none { it.assetId == assetId }) {
            candidate
        } else {
            candidate.copy(
                outputs = candidate.outputs.map { output ->
                    if (output.assetId == assetId) transform(output) else output
                },
            )
        }
    },
)
