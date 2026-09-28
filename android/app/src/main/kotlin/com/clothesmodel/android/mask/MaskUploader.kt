package com.clothesmodel.android.mask

import android.content.Context
import com.clothesmodel.android.data.ApiServices
import com.clothesmodel.android.data.ApiServicesFactory
import com.clothesmodel.android.data.AuthenticationEvents
import com.clothesmodel.android.data.Outcome
import com.clothesmodel.android.data.ProblemParser
import com.clothesmodel.android.data.networkProblem
import com.clothesmodel.contract.model.AssetKind
import com.clothesmodel.contract.model.UploadCompleteRequest
import com.clothesmodel.contract.model.UploadCreateRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MaskUploader @Inject constructor(
    @param:ApplicationContext private val context: Context,
    private val factory: ApiServicesFactory,
    private val events: AuthenticationEvents,
) {
    suspend fun upload(bytes: ByteArray): Outcome<UUID> = try {
        val services = factory.services() ?: return Outcome.AuthenticationExpired
        val token = UUID.randomUUID().toString()
        val create = services.uploads.createUploadSession(
            "mask-create-$token",
            UploadCreateRequest(
                assetKind = AssetKind.mask,
                filename = "mask.png",
                contentType = "image/png",
                sizeBytes = bytes.size.toLong(),
            ),
        )
        when {
            create.code() == 401 -> {
                events.onAuthenticationExpired()
                Outcome.AuthenticationExpired
            }

            !create.isSuccessful -> Outcome.Problem(ProblemParser.from(create.errorBody()))

            else -> {
                val session = create.body() ?: return Outcome.Problem(networkProblem())
                appendAndComplete(services, session.id, token, bytes)
            }
        }
    } catch (error: IOException) {
        Outcome.Problem(networkProblem())
    }

    private suspend fun appendAndComplete(
        services: ApiServices,
        uploadId: UUID,
        token: String,
        bytes: ByteArray,
    ): Outcome<UUID> {
        val file = File(context.cacheDir, "mask-upload-$uploadId.png")
        try {
            file.writeBytes(bytes)
            val append = services.uploads.appendUploadContent(uploadId, 0L, file)
            when {
                append.code() == 401 -> {
                    events.onAuthenticationExpired()
                    return Outcome.AuthenticationExpired
                }

                !append.isSuccessful -> return Outcome.Problem(ProblemParser.from(append.errorBody()))
            }
            val complete = services.uploads.completeUploadSession(
                uploadId,
                "mask-complete-$token",
                UploadCompleteRequest(sha256(bytes)),
            )
            return when {
                complete.code() == 401 -> {
                    events.onAuthenticationExpired()
                    Outcome.AuthenticationExpired
                }

                !complete.isSuccessful -> Outcome.Problem(ProblemParser.from(complete.errorBody()))

                complete.body() == null -> Outcome.Problem(networkProblem())

                else -> Outcome.Success(complete.body()!!.id)
            }
        } finally {
            runCatching { file.delete() }
        }
    }

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
}
