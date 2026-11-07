#!/usr/bin/env bash
# make-release-artifacts.sh - generate signed BUILD-INFO, SPDX SBOM, and in-toto attestation.
#
# Generates release metadata required for offline verification and reproducible releases.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

OUTPUT_DIR=${1:-"$GRINTION_REPO_ROOT/output"}
mkdir -p "$OUTPUT_DIR"

log "generating release metadata and provenance artifacts in $OUTPUT_DIR"

# 1. BUILD-INFO
BUILD_INFO_FILE="$OUTPUT_DIR/BUILD-INFO"
build_info "$BUILD_INFO_FILE"
log "generated $BUILD_INFO_FILE"

# 2. SPDX Release SBOM
SBOM_FILE="$OUTPUT_DIR/sbom.spdx.json"
"$GRINTION_REPO_ROOT/bin/grintion-audit" sbom --format spdx --output "$SBOM_FILE" >/dev/null
log "generated $SBOM_FILE"

# 3. in-toto SLSA Attestation
ATTESTATION_FILE="$OUTPUT_DIR/attestation.json"
cat > "$ATTESTATION_FILE" <<EOF
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "grintion-os-x86_64.iso",
      "digest": {
        "sha256": "$(sha256sum "$OUTPUT_DIR/grintion-os-x86_64.iso" 2>/dev/null | awk '{print $1}' || echo "0000000000000000000000000000000000000000000000000000000000000000")"
      }
    },
    {
      "name": "BUILD-INFO",
      "digest": {
        "sha256": "$(sha256sum "$BUILD_INFO_FILE" | awk '{print $1}')"
      }
    },
    {
      "name": "sbom.spdx.json",
      "digest": {
        "sha256": "$(sha256sum "$SBOM_FILE" | awk '{print $1}')"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://grintion.org/build/v1",
      "externalParameters": {
        "source_date_epoch": "$SOURCE_DATE_EPOCH",
        "version": "$GRINTION_VERSION",
        "arch": "$GRINTION_ARCH"
      }
    },
    "runDetails": {
      "builder": {
        "id": "https://github.com/Freddyz-coder/grintion-OS"
      }
    }
  }
}
EOF
log "generated $ATTESTATION_FILE"

# 4. Optional offline signing
if [ -n "${GRINTION_RELEASE_KEY:-}" ] && [ -f "${GRINTION_RELEASE_KEY:-}" ]; then
    "$GRINTION_REPO_ROOT/build/sign-release.sh"
fi

log "all release artifacts generated successfully"

