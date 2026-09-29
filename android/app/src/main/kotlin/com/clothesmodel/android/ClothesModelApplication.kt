package com.clothesmodel.android

import android.app.Application
import com.clothesmodel.contract.infrastructure.Serializer
import dagger.hilt.android.HiltAndroidApp
import kotlinx.serialization.ExperimentalSerializationApi

@HiltAndroidApp
class ClothesModelApplication : Application() {
    override fun onCreate() {
        configureContractSerialization()
        super.onCreate()
    }
}

@OptIn(ExperimentalSerializationApi::class)
internal fun configureContractSerialization() {
    Serializer.kotlinxSerializationJsonConfiguration = {
        explicitNulls = false
    }
}
