plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    api(libs.kotlinx.coroutines.android)
    api(libs.kotlinx.serialization.json)
    api(libs.retrofit.core)
    api(libs.retrofit.scalars)
    api(libs.retrofit.kotlinx.serialization)
    api(libs.okhttp)
    api(libs.okhttp.logging)
}
