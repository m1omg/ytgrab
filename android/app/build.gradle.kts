plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// One version number for every platform: the desktop package's own.
val appVersion: String = Regex("""__version__\s*=\s*"([^"]+)"""")
    .find(rootProject.file("../ytgrab/__init__.py").readText())!!.groupValues[1]
val versionParts = appVersion.split(".").map { it.toInt() }

// ffmpeg and QuickJS for each ABI, built by packaging/android/build_natives.sh.
val nativesDir = rootProject.file("natives")

// One APK per common phone architecture, plus one that runs everywhere.
val flavorAbis = mapOf(
    "arm64" to listOf("arm64-v8a"),
    "arm32" to listOf("armeabi-v7a"),
    "universal" to listOf("arm64-v8a", "armeabi-v7a", "x86", "x86_64"),
)

android {
    namespace = "dev.ytgrab.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.ytgrab.app"
        minSdk = 24
        targetSdk = 36
        versionCode = versionParts[0] * 10000 + versionParts[1] * 100 + versionParts[2]
        versionName = appVersion
    }

    flavorDimensions += "abi"
    productFlavors {
        flavorAbis.forEach { (name, abis) ->
            create(name) {
                dimension = "abi"
                ndk { abiFilters += abis }
            }
        }
    }

    signingConfigs {
        // CI passes the release key in; without it a release build stays unsigned.
        val keystore = System.getenv("YTGRAB_KEYSTORE")
        if (keystore != null) {
            create("release") {
                storeFile = file(keystore)
                // A pasted secret can carry a stray newline; the password has none.
                val password = System.getenv("YTGRAB_KEYSTORE_PASSWORD")?.trim()
                storePassword = password
                keyAlias = "ytgrab"
                keyPassword = password
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
    }

    sourceSets["main"].jniLibs.srcDir(nativesDir)

    packaging {
        // Android only runs programs from the unpacked native library folder,
        // so the helpers must be extracted rather than mapped from the APK.
        jniLibs.useLegacyPackaging = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

chaquopy {
    defaultConfig {
        // 3.11 is the newest Python Chaquopy still builds for 32-bit phones.
        version = "3.11"
        pip {
            // [default] brings the challenge solver scripts and yt-dlp's other
            // optional dependencies, each pinned to what this yt-dlp expects.
            install("yt-dlp[default]")
        }
    }
}

// An APK without ffmpeg or QuickJS would install fine and fail on the phone.
val checkNatives by tasks.registering {
    doLast {
        val missing = flavorAbis.values.flatten().distinct().flatMap { abi ->
            listOf("libffmpeg.so", "libqjs.so").map { nativesDir.resolve("$abi/$it") }
        }.filterNot { it.isFile }
        if (missing.isNotEmpty()) {
            throw GradleException(
                "Missing native helpers - run packaging/android/build_natives.sh <abi> " +
                    "android/natives/<abi> first:\n" + missing.joinToString("\n")
            )
        }
    }
}
tasks.named("preBuild") { dependsOn(checkNatives) }

// Newer AndroidX releases need compileSdk 37 and AGP 9; these are the last
// that build against API 36 with AGP 8.13.
dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.06.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.core:core-ktx:1.18.0")
}
