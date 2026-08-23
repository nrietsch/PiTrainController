#!/bin/sh
# Sanity-checks that the MCP25625 probed correctly and can0 is usable.
# Run after rebooting with the overlay installed (scripts/install_overlay.sh).
set -e

echo "== dmesg: mcp251x/can driver messages =="
dmesg | grep -i -E 'mcp251x|mcp25625|can0' || echo "(no matching dmesg lines -- overlay may not have loaded, see docs/INSTALL.md troubleshooting)"

echo ""
echo "== ip link: can0 =="
if ip link show can0 >/dev/null 2>&1; then
	ip -details -statistics link show can0
else
	echo "can0 does not exist. Check 'vcdbg log msg' / dmesg for overlay load errors, and confirm dtparam=spi=on and dtoverlay=pitraincontroller-mcp25625 are in /boot/firmware/config.txt."
	exit 1
fi

echo ""
echo "If can0 shows state UP and no errors above, bring it up (if not already, e.g. via the"
echo "pitraincontroller-can0.service unit) and try:"
echo "  candump can0            # watch for real traffic from the Gleisbox/CS2"
echo "  cansend can0 000#1122334455667788   # send a test frame"
