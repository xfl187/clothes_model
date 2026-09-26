# Android

Native Kotlin/Jetpack Compose engineering skeleton. Confirmed product UI remains governed by the Android UI Spec and `DESIGN.md`; this module contains only the Phase 1 contract proof.

## Modules

- `:app`: Material 3 shell, Hilt wiring, navigation placeholder, and app-owned `ContractStatusGateway` boundary.
- `:core:api-contract`: generated Retrofit/Kotlin serialization client. Sources are regenerated from the shared OpenAPI contract and must not be edited manually.

## Toolchain

- JDK 17
- Android SDK 37 / Build Tools 36.0.0
- Gradle 9.4.1 via the checked-in wrapper

Set `ANDROID_HOME` or create an ignored `local.properties` before building.

## Verification

```powershell
./gradlew.bat :core:api-contract:compileKotlin :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:assembleDebugAndroidTest :app:assembleRelease
./verify-release-boundary.ps1
```

The debug variant targets the host contract mock at `http://10.0.2.2:4010/` from an Android emulator. The endpoint, placeholder bearer token, and sample job ID are debug-only BuildConfig fields. Release fields are empty and the release verifier scans the APK for all three debug values.