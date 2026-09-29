package com.clothesmodel.android

import com.clothesmodel.contract.infrastructure.Serializer
import com.clothesmodel.contract.model.CreateJobRequest
import com.clothesmodel.contract.model.GenerationOptions
import com.clothesmodel.contract.model.TryOnMode
import java.util.UUID
import kotlinx.serialization.encodeToString
import org.junit.Assert.assertFalse
import org.junit.Test

class ContractSerializationTest {
    @Test
    fun optionalNullJobFieldsAreOmitted() {
        configureContractSerialization()
        val request = CreateJobRequest(
            personAssetIds = listOf(UUID.fromString("01992b5a-0000-7000-8000-000000000001")),
            garmentAssetId = UUID.fromString("01992b5a-0000-7000-8000-000000000002"),
            providerId = UUID.fromString("01992b5a-0000-7000-8000-000000000003"),
            mode = TryOnMode.precise_try_on,
            generationOptions = GenerationOptions(candidateCount = 1),
        )

        val encoded = Serializer.kotlinxSerializationJson.encodeToString(request)

        assertFalse(encoded.contains("\"mask_asset_id\""))
        assertFalse(encoded.contains("\"related_job_id\""))
        assertFalse(encoded.contains("\"advanced_parameters\""))
    }
}
