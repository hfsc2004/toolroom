# Toolroom Kiosk System - Project Summary

## Current Features
- **Persistent Kiosk Settings:** The screensaver idle timer is now saved to `localStorage`, persisting across reloads.
- **Improved Mouse Responsiveness:** Settings and UI elements use `mousedown` and surgical focus management to prevent "focus fighting" on Raspberry Pi hardware.
- **Dynamic Quantity Tally:** 
    - The Tally box is now a manual input field.
    - Added an "OPEN NUM PAD" command that reveals a 0-9 QR code grid.
    - Implemented a background "True Tally" variable to track bulk counts.

## Known Issues (The "Voodoo")
- **Command Leakage:** High-speed scanner bursts (like `CMD-OPEN-PAD`) occasionally "bleed" into active data fields (Badge/Item), resulting in partial strings like "CM" or "CMD" being left behind.
- **Race Conditions:** Despite implementing Burst-Buffer and Intercept logic, the Raspberry Pi's event loop occasionally processes `Enter` keys before the full command string is buffered, causing inconsistent command execution.
- **Field Wiping:** Commands scanned while a field is focused sometimes trigger a field reset due to how the browser handles rapid value changes during a focus shift.

## Next Steps
- Implement a more aggressive low-level key listener or consider a Node.js/Svelte architecture for better state-driven UI management.
- Refine the physical QR codes to ensure high contrast and clear scanning.
