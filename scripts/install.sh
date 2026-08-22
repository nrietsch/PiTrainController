#!/bin/sh
# Interactive installer: sets up the mandatory baseline (device tree
# overlay, can0, the Python package, the S88 driver, and the LED
# service), then asks which optional pieces to also install.
#
# Run with sudo on the target Raspberry Pi, from the repo root:
#   sudo scripts/install.sh
set -e

if [ "$(id -u)" -ne 0 ]; then
	echo "Run this as root (sudo scripts/install.sh)" >&2
	exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

ask_yn() {
	# ask_yn "question" default(y|n) -> sets $ANSWER to y or n
	question="$1"
	default="$2"
	if [ "$default" = "y" ]; then
		prompt="[Y/n]"
	else
		prompt="[y/N]"
	fi
	printf '%s %s ' "$question" "$prompt"
	read -r reply || reply=""
	reply=$(printf '%s' "$reply" | tr '[:upper:]' '[:lower:]')
	if [ -z "$reply" ]; then
		ANSWER="$default"
	elif [ "$reply" = "y" ] || [ "$reply" = "yes" ]; then
		ANSWER="y"
	else
		ANSWER="n"
	fi
}

echo "== PiTrainController installer =="
echo "Repo: $REPO_DIR"
echo ""

# --- 1. Mandatory baseline: overlay + can0 ---
echo "-- Device tree overlay + can0 --"
"$REPO_DIR/scripts/install_overlay.sh"

install -m 644 "$REPO_DIR/systemd/pitraincontroller-can0.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pitraincontroller-can0.service

# --- 2. Mandatory: Python package + system dependencies ---
echo ""
echo "-- Python package + dependencies --"
apt-get install -y python3-pip python3-can python3-lgpio 2>/dev/null || true
# apt just installed python3-can/python3-lgpio as Debian-managed packages
# (no pip RECORD manifest). --no-deps stops pip from trying to also
# resolve/reinstall those as pip dependencies -- without it, pip sees a
# version mismatch against the apt package, tries to uninstall it to
# replace it, and fails with "uninstall-no-record-file" since apt-managed
# packages aren't pip's to remove. This only installs our own package
# (pitraincontroller) editable, trusting apt for its two dependencies.
# --break-system-packages is appropriate here since these services run
# under the system python3, not a venv.
pip install --break-system-packages --no-deps -e "$REPO_DIR/python"

# --- 3. Mandatory: S88 driver + LED service ---
echo ""
echo "-- S88 driver + LED service --"
install -m 644 "$REPO_DIR/systemd/pitraincontroller-s88.service" /etc/systemd/system/
install -m 644 "$REPO_DIR/systemd/pitraincontroller-leds.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pitraincontroller-s88.service pitraincontroller-leds.service

# --- 4. Optional: CS2/CS3 LAN gateway ---
echo ""
ask_yn "Install the CS2/CS3 LAN gateway (lets Rocrail/CS2 App/other network clients control the layout through this Pi)?" y
if [ "$ANSWER" = "y" ]; then
	install -m 644 "$REPO_DIR/systemd/pitraincontroller-gateway.service" /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable pitraincontroller-gateway.service
	GATEWAY_INSTALLED=y
else
	echo "Skipping the CS2/CS3 gateway. You can install it later:"
	echo "  sudo install -m 644 $REPO_DIR/systemd/pitraincontroller-gateway.service /etc/systemd/system/"
	echo "  sudo systemctl daemon-reload && sudo systemctl enable --now pitraincontroller-gateway.service"
	GATEWAY_INSTALLED=n
fi

# --- 5. Optional: Rocrail ---
echo ""
ask_yn "Install Rocrail locally on this Pi (see docs/ROCRAIL.md for configuring it against can0)?" y
if [ "$ANSWER" = "y" ]; then
	apt-get install -y rocrail
	ROCRAIL_INSTALLED=y
else
	echo "Skipping Rocrail. Install later with: sudo apt install rocrail"
	ROCRAIL_INSTALLED=n
fi

echo ""
echo "== Done =="
echo "Reboot to load the overlay, then start the enabled services:"
echo "  sudo reboot"
echo "  scripts/verify_can0.sh"
echo "  sudo systemctl start pitraincontroller-can0 pitraincontroller-s88 pitraincontroller-leds"
if [ "$GATEWAY_INSTALLED" = "y" ]; then
	echo "  sudo systemctl start pitraincontroller-gateway"
fi
if [ "$ROCRAIL_INSTALLED" = "y" ]; then
	echo ""
	echo "Rocrail is installed but not auto-configured -- see docs/ROCRAIL.md"
	echo "to point it at can0 (or at this gateway, if installed)."
fi
