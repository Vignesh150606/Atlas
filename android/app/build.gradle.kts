plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.dagger.hilt.android")
    kotlin("kapt")
}

android {
    namespace = "com.atlas"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.atlas"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        // Phase 12 (docs/MASTER_PLAN.md #2.1): a hardcoded LAN IP used to
        // live here as a buildConfigField, requiring a source edit and a
        // rebuild to point at any other server, and requiring that IP to
        // also be added to network_security_config.xml's cleartext
        // allow-list - a step that was missed, so every request from the
        // installed APK failed. The server address is now a runtime
        // setting (see data/local/ServerConfigStore.kt, applied per-request
        // by di/BaseUrlInterceptor.kt, editable from Settings) - no build
        // field needed for it at all.
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        // AGP 8+ no longer generates the BuildConfig class by default.
        // Phase 12 removed the last custom buildConfigField (the hardcoded
        // LAN IP - see defaultConfig above), but this stays enabled since
        // AppModule.kt still reads the standard BuildConfig.DEBUG field to
        // gate HTTP logging (SECURITY_PLAN.md S3).
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation(platform("androidx.compose:compose-bom:2023.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    
    // Navigation
    implementation("androidx.navigation:navigation-compose:2.7.7")
    
    // Hilt
    implementation("com.google.dagger:hilt-android:2.50")
    kapt("com.google.dagger:hilt-compiler:2.50")
    implementation("androidx.hilt:hilt-navigation-compose:1.1.0")

    // WorkManager (Phase 11 section 2: Proactive Suggestions background check)
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    implementation("androidx.hilt:hilt-work:1.1.0")
    kapt("androidx.hilt:hilt-compiler:1.1.0")

    // Phase 12 / SECURITY_PLAN.md S4: EncryptedSharedPreferences for the
    // API key and server URL (data/local/ApiKeyStore.kt,
    // data/local/ServerConfigStore.kt) - previously plain MODE_PRIVATE
    // SharedPreferences, readable on a rooted device or via an unlocked
    // device backup path.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Retrofit
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation(platform("androidx.compose:compose-bom:2023.10.01"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
