# Multi-stage Node.js Dockerfile (multi-arch friendly)
# - Base image: node:lts-slim (official tag)
# - Builder stage: installs dev deps (npm ci) and runs the build
# - Final stage: copies only runtime artifacts, runs as non-root 'node' user

ARG NODE_IMAGE=node:lts-slim
FROM ${NODE_IMAGE} AS builder

# Set working dir
WORKDIR /usr/src/app

# Copy only package manifests first to leverage Docker cache for npm install
COPY package*.json ./

# Install all dependencies (dev + prod) for the build step
RUN npm ci --silent

# Copy source files
COPY . .

# Default build directory (can be overridden at build time)
ARG BUILD_DIR=dist
ENV BUILD_DIR=${BUILD_DIR}

# Run the project build if present. --if-present makes this step a no-op when
# there's no build script defined in package.json (keeps image build stable).
RUN npm run build --if-present

# Optionally run tests in builder stage (uncomment in CI when needed)
# RUN npm test --if-present

# ---- Final image ----
FROM ${NODE_IMAGE} AS runner

WORKDIR /usr/src/app

# Copy production runtime files from builder. Use --chown to ensure non-root user
# will be able to read/write as needed.
ARG BUILD_DIR=dist
ENV BUILD_DIR=${BUILD_DIR}

# Copy package files so metadata is available in final image
COPY --from=builder --chown=node:node /usr/src/app/package*.json ./

# Copy node_modules from builder to avoid reinstalling in the final image
# (preserves exact installed artifacts from builder stage)
COPY --from=builder --chown=node:node /usr/src/app/node_modules ./node_modules

# Copy build output (default: dist) into image
COPY --from=builder --chown=node:node /usr/src/app/${BUILD_DIR} ./${BUILD_DIR}

# Set production env
ENV NODE_ENV=production
ENV PORT=3000
EXPOSE ${PORT}

# Use the official non-root 'node' user provided by the base image
USER node

# Default runtime command. Use shell form so environment expansion works for BUILD_DIR.
# Adjust the path if your project emits a different entrypoint (e.g. server.js, index.mjs).
CMD ["sh", "-c", "node ${BUILD_DIR}/index.js"]
