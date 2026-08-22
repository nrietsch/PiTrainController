#!/bin/sh
# Interactive installer: sets up the mandatory baseline (device tree
# overlay, can0, the Python package, the S88 driver, and the LED
# service), then asks which optional pieces to also install.
#
# Uses whiptail (raspi-config's own menu tool, preinstalled on Raspberry
# Pi OS) for the LED reference info and the optional-component picker if
# it's available; falls back to plain y/n prompts otherwise (e.g. a
# minimal image, or a non-interactive run).
#
# Run with sudo on the target Raspberry Pi, from the repo root:
#   sudo scripts/install.sh
set -e

if [ "$(id -u)" -ne 0 ]; then
	echo "Run this as root (sudo scripts/install.sh)" >&2
	exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# The user who ran `sudo` -- used for anything that should land in a real
# home directory / real desktop session (Rocrail's setup) rather than
# root's. Falls back to the current user if not run via sudo (e.g.
# logged in as root directly), which is a reasonable-enough edge case.
TARGET_USER="${SUDO_USER:-$(id -un)}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

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

command -v whiptail >/dev/null 2>&1 || apt-get install -y whiptail >/dev/null 2>&1 || true
if command -v whiptail >/dev/null 2>&1; then
	HAVE_WHIPTAIL=y
else
	HAVE_WHIPTAIL=n
fi

echo "== PiTrainController installer =="
echo "Repo: $REPO_DIR"
echo ""

if [ "$HAVE_WHIPTAIL" = "y" ]; then
	whiptail --title "PiTrainController -- LED reference" --msgbox "\
Four status LEDs on the board (see docs/reference/hardware-manual-v4.md,\
 section 4, for the full behavior spec):

  LED1  Blue    GPIO5   (pin 29)  CAN bus activity
  LED2  Green   --      (n/a)     Power present (passive, no GPIO)
  LED3  Orange  GPIO12  (pin 32)  S88 poll activity
  LED4  Red     GPIO6   (pin 31)  Boot / heartbeat / fault

Press Enter to continue with setup." 16 74
fi

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
# under the system python3, not a venv. --root-user-action=ignore just
# quiets pip's (accurate, but expected here) warning about running as root.
pip install --break-system-packages --root-user-action=ignore --no-deps -e "$REPO_DIR/python"

# --- 3. Mandatory: S88 driver + LED service ---
echo ""
echo "-- S88 driver + LED service --"
install -m 644 "$REPO_DIR/systemd/pitraincontroller-s88.service" /etc/systemd/system/
install -m 644 "$REPO_DIR/systemd/pitraincontroller-leds.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pitraincontroller-s88.service pitraincontroller-leds.service

# --- 4. Optional components: pick which to install ---
echo ""
if [ "$HAVE_WHIPTAIL" = "y" ]; then
	SELECTED=$(whiptail --title "PiTrainController -- optional components" --checklist \
		"Space to toggle, Enter to confirm:" 15 78 2 \
		"gateway" "CS2/CS3 LAN gateway (Rocrail/CS2 App/network clients via UDP 15731)" ON \
		"rocrail" "Rocrail (local GUI control on this Pi)" ON \
		3>&1 1>&2 2>&3) || SELECTED=""

	case "$SELECTED" in
		*gateway*) GATEWAY_ANSWER=y ;;
		*) GATEWAY_ANSWER=n ;;
	esac
	case "$SELECTED" in
		*rocrail*) ROCRAIL_ANSWER=y ;;
		*) ROCRAIL_ANSWER=n ;;
	esac
	echo "Selected: gateway=$GATEWAY_ANSWER rocrail=$ROCRAIL_ANSWER"
else
	ask_yn "Install the CS2/CS3 LAN gateway (lets Rocrail/CS2 App/other network clients control the layout through this Pi)?" y
	GATEWAY_ANSWER="$ANSWER"
	ask_yn "Install Rocrail locally on this Pi (see docs/ROCRAIL.md for configuring it against can0)?" y
	ROCRAIL_ANSWER="$ANSWER"
fi

# --- Apply: CS2/CS3 LAN gateway ---
if [ "$GATEWAY_ANSWER" = "y" ]; then
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

# --- Apply: Rocrail ---
# Not an apt package on Raspberry Pi OS/Debian -- ships as a snapshot zip
# with its own setup script (see docs/ROCRAIL.md). desktoplink.sh wants a
# real logged-in desktop session to set up the launcher correctly, so we
# download/extract it (safe to do headlessly, into the invoking user's
# home directory) but leave running desktoplink.sh itself as a manual
# last step rather than guessing at a session that may not exist here.
if [ "$ROCRAIL_ANSWER" = "y" ]; then
	echo "Rocrail isn't an apt package -- downloading the Debian 13 (Trixie) snapshot build for $TARGET_USER..."
	apt-get install -y libevdev2 libinput10
	ROCRAIL_ZIP="$TARGET_HOME/Rocrail-debian13-ARM64.zip"
	ROCRAIL_DIR="$TARGET_HOME/Rocrail-debian13-ARM64"
	if sudo -u "$TARGET_USER" wget -q -O "$ROCRAIL_ZIP" \
		https://wiki.rocrail.net/rocrail-snapshot/Rocrail-debian13-ARM64.zip; then
		sudo -u "$TARGET_USER" mkdir -p "$ROCRAIL_DIR"
		sudo -u "$TARGET_USER" unzip -q -o "$ROCRAIL_ZIP" -d "$ROCRAIL_DIR"
		ROCRAIL_INSTALLED=y
		ROCRAIL_NEEDS_DESKTOPLINK=y
	else
		echo "Download failed (rolling snapshot URL may have changed) -- see docs/ROCRAIL.md" \
			"for the current download link and finish this manually."
		ROCRAIL_INSTALLED=n
	fi
else
	echo "Skipping Rocrail. See docs/ROCRAIL.md to install it later."
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
	echo "Rocrail was downloaded to $ROCRAIL_DIR but NOT fully set up yet --"
	echo "desktoplink.sh needs to run from a real desktop terminal (not this"
	echo "sudo/SSH session) to register the launcher correctly:"
	echo "  cd $ROCRAIL_DIR && sh ./desktoplink.sh"
	echo "Then see docs/ROCRAIL.md to point it at can0."
fi
