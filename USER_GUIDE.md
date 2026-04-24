# HarmonicDrive User Guide

HarmonicDrive is a near-field acoustic scanner controller featuring a real-time web-based UI. It automates loudspeaker 
measurements by moving a microphone along predefined grids (e.g. cylindrical or spherical) using a 3-axis CNC-style turntable/arm.

---

## 1. Getting Started


## Prerequisites
1.  The grbl settings have been set correctly using external tooling (e.g. IOSender).

### Installation
1.  **Clone Repositories**: Ensure both `HarmonicDrive` and the `NFS` library are cloned into adjacent directories.
2.  **Sync Dependencies**: Use `uv` to manage the environment.
    ```bash
    cd HarmonicDrive
    uv sync
    ```
3.  **Launch the UI**:
    ```bash
    uv run main.py
    ```
    The UI will be automatically opened. In case it isn't, it is accessible at `http://localhost:8080`.

---

## 2. Configuration (`config.ini`)

The `config.ini` file controls all hardware and software parameters.

### `[scanner]`
- `controller`: Type of motion controller (typically `grbl_streamer`).
- `feed_rate`: Global movement speed limit in mm/min.

### `[motion_manager]`
- `type`: The class name for motion logic (e.g., `CylindricalMeasurementMotionManager`).
- `measurement_points`: Reference to the section defining the grid.
- `safe_radius`: Minimum distance maintained to prevent collisions.

### `[audio]` & `[sweep]`
- `mode`: Set to `hardware` for real measurements or `mock` for testing without hardware.
- `in_dev` / `out_dev`: Audio interface device indices.
- `sweep_dur_s`: Length of the exponential sweep.
- `num_sweeps`: Number of captures to average per point to improve SNR.
- `naming_convention`: File naming format for recordings (`tom` or `dimitri`).

---

## 3. The GUI Interface

The UI is divided into two main panels: **Controls (Left)** and **Plots (Right)**.

### Jog Controls
- **PHI (Rotation)**: Rotates the turntable. Buttons are labeled with step sizes (1, 10, 60, 120 degrees). `CW` (Clockwise) and `CCW` (Counter-Clockwise).
- **R (Radius)**: Moves the arm in/out. `IN` moves towards the center, `OUT` moves away.
- **Z (Height)**: Moves the microphone up/down.
- **STOP (HOLD)**: Red button in the center of each jog row to immediately halt that axis.

### System Commands
- **HOME**: Initiates the hardware homing sequence. Turns **Green** when successful, **Orange** if homing is required.
- **Clear Alarm**: Resets the GRBL "Alarm" state (often triggered by hitting limit switches).
- **Soft Reset**: Resets the GRBL controller firmware.
- **REHOME**: Forces a re-homing sequence. This is useful if the GRBL firmware is stuck in an alarm state.
- **HOLD**: Immediate pause for all motion.

### Setup & Measurement
- **Height Offset**: Enter the distance (mm) from the turntable stool to the speaker's acoustic center.
- **Set height offset**: Applies the value to the current coordinate system.
- **Zero NFS**: Critical step. Sets the current position as the "Zero" reference and applies the height offset.
- **Start measurements**: Begins the automated scan through all grid points.
- **Take single measurement**: Captures a single sweep at the current position.

### Live Displays
- **Position Dials**: Real-time readout of Radius (R), Theta (PHI), and Height (Z).
- **Status**: Current machine state (Idle, Run, Alarm, etc.).
- **Live Plot**: A scatter plot showing measured points in Azimuth vs. Elevation space.
- **Log View**: Accessible via **Show Logs**. Displays real-time system events and errors.

---

## 4. Recommended Workflow

Follow these steps for a successful measurement session:

1.  **Hardware Prep**: Mount the speaker on the turntable and the microphone on the arm. Make sure everything is properly aligned. Etc, etc.
2.  **Home the System**: Click **HOME** and wait for the button to turn green and the status to show `IDLE`.
3.  **Manual Alignment**:
    - Use the Jog buttons to move the microphone until it is perfectly aligned with the zero-triangle.
4.  **Set Reference**:
    - Enter the **Height Offset** (distance from the stool surface to the reference point).
    - Click **Zero NFS**. The coordinate system will now center on your speaker.
5.  **Run Scan**:
    - Click **Start measurements**. 
    - Monitor the **Live Plot** and **Log View** to ensure measurements are proceeding as expected.
    - WAV files will be saved to the `measurements/` folder automatically with the time and date encoded in the directory.

---

## 5. Troubleshooting

- **Machine in ALARM**: Usually caused by hitting a limit switch or a hard stop. Click **Clear Alarm**. If it persists, use **Soft Reset**.
- **Audio Errors**: Check the `[audio]` section in `config.ini`. Ensure the `in_dev` and `out_dev` match the indices found by running `python list_sound_devices.py`.
- **Unexpected Movement**: Verify `steps_per_millimeter` in the configuration. Check if the axes are reversed in the GRBL settings.
- **UI Unresponsive**: Refresh the browser page. The backend `main.py` should remain running.
