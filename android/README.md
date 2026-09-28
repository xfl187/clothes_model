# Android

Native Kotlin/Jetpack Compose application. Confirmed product UI is governed by the Android UI Spec and `DESIGN.md`. Phase 6 completed the Android V1 product surface: fixed `首页 / 素材 / 历史` navigation, asset library with durable imports, the three-step precise-try-on wizard, job detail/recovery/lineage, results with comparison/download/share/deletion, and the mask editor.

## Modules

- `:app`: Material 3 application with Hilt wiring, Quiet Atelier theme, navigation, feature packages (`home`, `assets`, `create`, `jobs`, `results`, `mask`), the authenticated `data` boundary, and `imports` persistence.
- `:core:api-contract`: generated Retrofit/Kotlin serialization client. Sources are regenerated from the shared OpenAPI contract and must not be edited manually.

## Toolchain

- JDK 17
- Android SDK 37 / Build Tools 36.0.0
- Gradle 9.4.1 via the checked-in wrapper

Set `ANDROID_HOME` or create an ignored `local.properties` before building.

## Verification

Run the deterministic Phase 6 exit gate from the repository root:

```powershell
pwsh -File android/verify-phase6.ps1
```

Or run the Android gates directly:

```powershell
./gradlew.bat :core:api-contract:compileKotlin :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:assembleDebugAndroidTest :app:assembleRelease
./verify-release-boundary.ps1
```

Compose instrumentation tests cover navigation, the asset center, home/history, the creation wizard, job detail, results/compare, and the mask editor. They compile in this repository and execute in the CI emulator jobs.

The debug variant targets the host contract mock at `http://10.0.2.2:4010/` from an Android emulator. The endpoint, placeholder bearer token, and sample job ID are debug-only BuildConfig fields. Release fields are empty and the release verifier scans the APK for all three debug values.
