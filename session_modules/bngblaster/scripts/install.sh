#!/usr/bin/env bash
set -euo pipefail

REPO="rtbrick/bngblaster"
BNGBLASTER_VERSION="0.9.17"  # Use 0.9.39 starting with Ubuntu 22.04.
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release

  if [[ "${ID:-}" == "ubuntu" ]]; then
    ubuntu_major="${VERSION_ID%%.*}"
    ubuntu_minor="${VERSION_ID#*.}"
    ubuntu_minor="${ubuntu_minor%%.*}"

    if [[ "$ubuntu_major" =~ ^[0-9]+$ && "$ubuntu_minor" =~ ^[0-9]+$ ]]; then
      ubuntu_major=$((10#$ubuntu_major))
      ubuntu_minor=$((10#$ubuntu_minor))

      if (( ubuntu_major > 22 || (ubuntu_major == 22 && ubuntu_minor >= 4) )); then
        BNGBLASTER_VERSION="0.9.39"
      fi
    fi
  fi
fi
# was "v${BNGBLASTER_VERSION}"
BNGBLASTER_TAG="${BNGBLASTER_VERSION}"


current_user=$USER
add_sudo_rights() {
  current_user=$USER
  if (sudo -l | grep -q '(ALL : ALL) SETENV: NOPASSWD: '$1); then
    echo 'visudo entry already exists';
  else
    sleep 0.1
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:SETENV:'$1 | sudo EDITOR='tee -a' visudo;
  fi
}



TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

log() {
    echo "[*] $*"
}

fail() {
    echo "[!] $*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

log "Checking operating system..."
if [[ ! -f /etc/os-release ]]; then
    fail "/etc/os-release not found"
fi

# shellcheck disable=SC1091
. /etc/os-release

if [[ "${ID:-}" != "ubuntu" ]]; then
    fail "This script is intended for Ubuntu. Detected: ${ID:-unknown}"
fi

UBUNTU_VERSION_ID="${VERSION_ID:-}"
UBUNTU_VERSION_MAJOR="${UBUNTU_VERSION_ID%%.*}"

log "Detected Ubuntu ${UBUNTU_VERSION_ID}"

require_cmd curl
require_cmd dpkg
require_cmd apt-get
require_cmd grep
require_cmd sed
require_cmd head

INSTALLED_VERSION=""
if command -v bngblaster >/dev/null 2>&1; then
    INSTALLED_VERSION="$(bngblaster -v | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
    log "Installed version: ${INSTALLED_VERSION:-unknown}"
else
    log "BNG Blaster not installed"
fi

if [[ -n "$INSTALLED_VERSION" ]]; then
    if dpkg --compare-versions "$INSTALLED_VERSION" eq "$BNGBLASTER_VERSION"; then
        log "BNG Blaster ${INSTALLED_VERSION} is already installed. Skipping."
        printf "Adding the following entries to visudo at ***BNGBlaster Host***:"
        add_sudo_rights $(which bngblaster)
        exit 0
    elif dpkg --compare-versions "$INSTALLED_VERSION" gt "$BNGBLASTER_VERSION"; then
        log "Installed version ${INSTALLED_VERSION} is newer than pinned version ${BNGBLASTER_VERSION}. Skipping."
        exit 0
    else
        log "Updating: $INSTALLED_VERSION -> $BNGBLASTER_VERSION"
    fi
fi

log "Installing dependencies..."
sudo apt-get update

if [[ "$UBUNTU_VERSION_MAJOR" -le 20 ]]; then
    sudo apt-get install -y curl ca-certificates libssl1.1 libncurses5 libjansson4
else
    sudo apt-get install -y curl ca-certificates libssl3 libncurses6 libjansson4
fi

log "Fetching release metadata for ${BNGBLASTER_TAG}..."
RELEASE_JSON="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/tags/${BNGBLASTER_TAG}")"

DEB_URL="$(
    printf '%s\n' "$RELEASE_JSON" \
    | grep -oE '"browser_download_url":[[:space:]]*"[^"]+\.deb"' \
    | sed -E 's/^"browser_download_url":[[:space:]]*"//; s/"$//' \
    | head -n1
)"

if [[ -z "$DEB_URL" ]]; then
    fail "Could not find .deb asset for version ${BNGBLASTER_VERSION}"
fi

DEB_FILE="${TMP_DIR}/$(basename "$DEB_URL")"

log "Downloading $(basename "$DEB_URL")..."
curl -fL "$DEB_URL" -o "$DEB_FILE"

log "Installing package..."
sudo dpkg -i "$DEB_FILE" || sudo apt-get install -y

# install controller => runs automatically after install
wget https://github.com/rtbrick/bngblaster-controller/releases/download/0.1.3/bngblaster-controller_0.1.3_amd64.deb
sudo dpkg -i bngblaster-controller_0.1.3_amd64.deb
rm dpkg -i bngblaster-controller_0.1.3_amd64.deb

systemctl start rtbrick-bngblasterctrl.service
systemctl status rtbrick-bngblasterctrl.service



log "Verifying installation..."
if command -v bngblaster >/dev/null 2>&1; then
    log "Installed: $(command -v bngblaster)"
    bngblaster --version || true

    printf "Adding the following entries to visudo at ***BNGBlaster Host***:"
    add_sudo_rights $(which bngblaster)
else
    fail "Installation failed"
fi


