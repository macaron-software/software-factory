FROM eclipse-temurin:17-jdk-jammy

ARG ANDROID_SDK_VERSION=11076708
ARG ANDROID_BUILD_TOOLS=35.0.0
ARG ANDROID_PLATFORM=android-35
ARG EMULATOR_SYSTEM_IMAGE=system-images;android-35;google_apis;x86_64

ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"

# System deps for emulator
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip git libpulse0 libgl1 libnss3 libxcomposite1 \
    libxcursor1 libxi6 libxtst6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Android command-line tools
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    curl -sSL "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_SDK_VERSION}_latest.zip" \
      -o /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d /tmp/cmdline-tools && \
    mv /tmp/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest && \
    rm -rf /tmp/cmdline-tools.zip /tmp/cmdline-tools

# Accept licenses + install SDK components
RUN yes | sdkmanager --licenses > /dev/null 2>&1 && \
    sdkmanager --update && \
    sdkmanager \
      "platform-tools" \
      "build-tools;${ANDROID_BUILD_TOOLS}" \
      "platforms;${ANDROID_PLATFORM}" \
      "emulator" \
      "${EMULATOR_SYSTEM_IMAGE}"

# Create AVD for headless testing
RUN echo "no" | avdmanager create avd \
    --name test_avd \
    --package "${EMULATOR_SYSTEM_IMAGE}" \
    --device "pixel_6" \
    --force

# Gradle wrapper cache dir
RUN mkdir -p /root/.gradle

# Workspace mount point
VOLUME /workspace

WORKDIR /workspace

# Healthcheck: verify SDK is installed
HEALTHCHECK --interval=30s --timeout=5s \
    CMD sdkmanager --list_installed | grep -q "platform-tools" || exit 1

# Keep container alive for docker exec
CMD ["tail", "-f", "/dev/null"]
