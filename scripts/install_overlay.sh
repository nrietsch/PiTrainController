#!/bin/sh
# Compiles and installs the PiTrainController MCP25625 device tree overlay,
# and appends the required config.txt lines if they aren't already present.
#
# Run with sudo on the target Raspberry Pi:
#   sudo scripts/install_overlay.sh
set -e

if [ "$(id -u)" -ne 0 ]; then
	echo "Run this as root (sudo scripts/install_overlay.sh)" >&2
	exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OVERLAY_SRC="$REPO_DIR/overlays/pitraincontroller-mcp25625.dts"
OVERLAY_DTBO="/boot/firmware/overlays/pitraincontroller-mcp25625.dtbo"
CONFIG_TXT="/boot/firmware/config.txt"
CONFIG_SNIPPET="$REPO_DIR/config/config.txt.snippet"

if [ ! -f "$CONFIG_TXT" ]; then
	echo "Expected $CONFIG_TXT (Bookworm/Trixie boot layout) but it's not there." >&2
	echo "If this is an older image with /boot/config.txt instead, edit this script's CONFIG_TXT path." >&2
	exit 1
fi

command -v dtc >/dev/null 2>&1 || { echo "dtc not found. Install with: sudo apt install device-tree-compiler" >&2; exit 1; }

echo "Compiling overlay..."
dtc -@ -I dts -O dtb -o "$OVERLAY_DTBO" "$OVERLAY_SRC"

echo "Installed overlay to $OVERLAY_DTBO"

if grep -q '^dtoverlay=pitraincontroller-mcp25625' "$CONFIG_TXT"; then
	echo "$CONFIG_TXT already references pitraincontroller-mcp25625, leaving it alone."
else
	echo "" >> "$CONFIG_TXT"
	echo "# --- PiTrainController (added by scripts/install_overlay.sh) ---" >> "$CONFIG_TXT"
	cat "$CONFIG_SNIPPET" | grep -v '^#' | grep -v '^$' >> "$CONFIG_TXT"
	echo "Appended overlay config to $CONFIG_TXT"
fi

echo ""
echo "Done. Reboot for the overlay to take effect, then verify with:"
echo "  scripts/verify_can0.sh"
