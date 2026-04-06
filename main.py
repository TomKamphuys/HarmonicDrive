from nicegui import app, ui, run
import argparse
import numpy as np
import asyncio
import time
import threading
import queue
import ctypes
import soundfile as sf
from pathlib import Path

from loguru import logger

from nfs import NearFieldScannerFactory, ScannerFactory
from nfs.logging_config import setup_logging

# --- 7-segment look: load digital-ish font ---
# Orbitron is a popular "tech" font available on Google Fonts.
# Digital-7 or segment fonts aren't standard, but VT323/Share Tech Mono/Press Start 2P work well.
ui.add_head_html('<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">')

log_handler = None


# --- Loguru: setup handled by nfs.logging_config ---
# We keep log_button_click for UI events.

def log_button_click(label: str, handler):
    """Wrap a NiceGUI on_click handler to log the click and then run it (sync or async)."""

    async def _wrapped(*args, **kwargs):
        logger.info("UI click: {}", label)
        result = handler(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result

    return _wrapped


# --- Dedicated Audio Worker Thread (ASIO Fix) ---
# This worker ensures all ASIO calls happen on one consistent thread with COM initialized.
audio_queue = queue.Queue()


def audio_worker():
    """A dedicated thread with COM initialization for picky ASIO drivers."""
    try:
        # Initialize COM for this thread (COINIT_APARTMENTTHREADED = 2)
        ctypes.windll.ole32.CoInitializeEx(None, 2)
        logger.info("Audio worker thread COM initialized.")
    except Exception as e:
        logger.warning(f"COM initialization failed: {e}")

    while True:
        item = audio_queue.get()
        if item is None:
            break

            # Unpack the 4 items, including the specific asyncio loop
        func, args, done_event, loop = item
        try:
            func(*args)
        except StopIteration:
            # Handle the "No more points" signal from FileMeasurementPoints.next()
            logger.info("Measurement sequence completed: All points processed successfully.")
        except Exception as e:
            # Catch cases where it might be raised as a standard Exception instead of StopIteration
            if "No more points" in str(e):
                logger.info("Measurement sequence completed: All points processed successfully.")
            else:
                logger.error(f"Audio worker failed: {e}")
        finally:
            # This ensures the UI buttons re-enable even if an error occurs
            loop.call_soon_threadsafe(done_event.set)
            audio_queue.task_done()

    try:
        ctypes.windll.ole32.CoUninitialize()
    except:
        pass


# Start the daemon worker thread immediately
worker_thread = threading.Thread(target=audio_worker, daemon=True)
worker_thread.start()

# --- CSS Styles ---
ui.add_css("""
@keyframes alarm_blink {
  0%   { opacity: 1; }
  50%  { opacity: 0.15; }
  100% { opacity: 1; }
}
.alarm_blink {
  animation: alarm_blink 0.6s linear infinite;
}

/* --- Jog button rows (like the reference image) --- */
.jog-grid {
  display: grid;
  grid-template-columns: 64px repeat(4, 72px) 72px repeat(4, 72px);
  gap: 6px;
  align-items: center;
}
.jog-hdr {
  font-size: 0.85rem;
  font-weight: 600;
  color: #374151;
}
.jog-hdr-left  { grid-column: 2 / span 4; text-align: left; }
.jog-hdr-stop  { grid-column: 6; text-align: center; }
.jog-hdr-right { grid-column: 7 / span 4; text-align: right; }

.jog-axis {
  font-weight: 800;
  color: #111827;
  line-height: 1.05;
}
.jog-unit {
  font-size: 0.75rem;
  font-weight: 700;
  color: #374151;
  margin-top: 2px;
}

.jog-btn {
  width: 72px;
  min-height: 38px;
  font-weight: 800;
}
.jog-stop {
  width: 72px;
  min-height: 38px;
  font-weight: 900;
}

/* --- Command buttons row (HOME / Clear Alarm / Soft Reset / REHOME / HOLD) --- */
.cmd-row {
  display: grid;
  grid-template-columns: repeat(5, 120px);
  gap: 18px;
  align-items: stretch;
}

/* Base command button style: DO NOT force background color here
   (so Quasar "color=orange/green" can work for HOME). */
.cmd-btn {
  min-height: 56px;
  font-weight: 800;
  letter-spacing: 0.5px;
}

/* Blue style for the other command buttons (like the reference) */
.cmd-btn-blue {
  background: #8fa9db !important;
  color: #0b1220 !important;
  border: 1px solid #5d6b86 !important;
}
""")


def start_nfs():
    pass


def stop_nfs():
    print('Stopping NFS')
    try:
        # Signal audio thread to exit
        audio_queue.put(None)
        nfs.shutdown()
    except Exception as e:
        print(f"Error during shutdown: {e}")


def hold_scanner():
    """Stop motion only (do NOT stop NFS)."""
    try:
        scanner.hold()
    except Exception as e:
        print(f"Error during HOLD: {e}")


def DEMO_move_to_stool():
    scanner.planar_move_to(-500.0, -500.0)


# This is the correct way to register the shutdown hook
app.on_shutdown(stop_nfs)


def rehome():
    scanner.softreset()
    time.sleep(1)
    scanner.clear_alarm()
    time.sleep(1)
    scanner.home()


async def take_measurement():
    # Not used directly in UI anymore, but kept for reference
    nfs.take_measurement_set()


async def async_task():
    """Offload measurement set to dedicated audio thread."""
    ui.notify('Measurement started')
    for button in greyable_buttons:
        button.disable()

    try:
        # Capture the actual running loop
        loop = asyncio.get_running_loop()
        done = asyncio.Event()
        # Send the task to the queue: (function, args, event, loop)
        audio_queue.put((nfs.take_measurement_set, (), done, loop))
        # Wait for the worker to signal completion
        await done.wait()
    except Exception as e:
        logger.error(f"Measurement task failed: {e}")
        ui.notify(f"Error: {e}", type='negative')
    finally:
        # Use finally to ensure buttons re-enable even if the task fails
        ui.notify('Measurement finished')
        for button in greyable_buttons:
            button.enable()


async def async_single_measurement_task():
    """Offload single measurement to dedicated audio thread."""
    ui.notify('Single measurement started')
    for button in greyable_buttons:
        button.disable()

    try:
        # Capture the actual running loop
        loop = asyncio.get_running_loop()
        done = asyncio.Event()
        # Send the task to the queue: (function, args, event, loop)
        audio_queue.put((nfs.take_single_measurement, (), done, loop))
        await done.wait()
    except Exception as e:
        logger.error(f"Single measurement failed: {e}")
        ui.notify(f"Error: {e}", type='negative')
    finally:
        ui.notify('Single measurement finished')
        for button in greyable_buttons:
            button.enable()


async def safe_move(func, *args):
    """Wrapper to disable UI, run a hardware command, then re-enable UI"""
    for button in greyable_buttons:
        button.disable()
    try:
        await run.io_bound(func, *args)
    finally:
        for button in greyable_buttons:
            button.enable()


async def zero_nfs_then_apply_height_offset(height_value: float):
    """Zero NFS, then apply the given height offset above stool."""
    await run.io_bound(scanner.set_as_zero)
    await run.io_bound(scanner.set_speaker_center_above_stool, height_value)


def load_measurement_data():
    """Load cylindrical coordinates from measurement_positions.csv and convert to azimuth/elevation"""
    file_path = Path('measurement_positions.csv')
    if not file_path.exists():
        return None, None

    try:
        data = np.loadtxt(file_path, delimiter=',', skiprows=1)
        data = np.atleast_2d(data)  # <--- Add this line
        if data.size == 0:
            return None, None

        r = data[:, 0]
        theta = data[:, 1]  # This is azimuth (theta)
        z = data[:, 2]

        # Calculate elevation angle from cylindrical coordinates
        elevation = np.degrees(np.arctan2(z, r))

        # Azimuth is already theta
        azimuth = theta

        return azimuth, elevation
    except Exception as e:
        print(f"Error loading data: {e}")
        return None, None


def update_plot():
    """Update the 2D plot with azimuth and elevation data"""
    azimuth, elevation = load_measurement_data()

    fig.clear()
    fig.set_layout_engine('constrained')
    ax = fig.add_subplot(111)

    if azimuth is not None and elevation is not None:
        scatter = ax.scatter(azimuth, elevation, c=elevation, cmap='viridis', marker='o', s=20)
        ax.set_xlabel('Azimuth (degrees)')
        ax.set_ylabel('Elevation (degrees)')
        ax.set_title('Measurement Points (Azimuth vs Elevation)')

        # Set axis limits
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)

        # Add colorbar
        fig.colorbar(scatter, ax=ax, label='Elevation (degrees)')

        # Add grid for better readability
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0, 0, 'No data available',
                horizontalalignment='center', verticalalignment='center')
        ax.set_xlabel('Azimuth (degrees)')
        ax.set_ylabel('Elevation (degrees)')
        ax.set_title('Waiting for data...')
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.grid(True, alpha=0.3)

    plot.update()


def update_ir_fr_plots(ir_plot_container):
    """
    Finds the latest *_ir.wav in ./Recordings, loads it,
    calculates the Frequency Response, and updates the IR and FR plots.
    - Zoom: 15ms
    - Peak at 1/4 of the axis.
    """
    rec_dir = Path('./Recordings')
    if not rec_dir.exists():
        return

    # Find the latest linear IR file
    wav_files = list(rec_dir.glob('*_ir.wav'))
    if not wav_files:
        return

    latest_file = max(wav_files, key=lambda f: f.stat().st_mtime)

    try:
        ir, fs = sf.read(str(latest_file))
        if len(ir.shape) > 1:
            ir = ir[:, 0]  # mono only
    except Exception as e:
        logger.error(f"Error loading IR: {e}")
        return

    # Find peak and define zoom window (15ms, peak at 1/4)
    zoom_ms = 15.0
    zoom_samples = int((zoom_ms / 1000.0) * fs)
    peak_idx = np.argmax(np.abs(ir))

    start_idx = max(0, peak_idx - int(zoom_samples / 4))
    end_idx = start_idx + zoom_samples

    ir_zoom = ir[start_idx:end_idx]
    time_axis = (np.arange(len(ir_zoom)) / fs) * 1000.0  # ms

    # Calculate Frequency Response (FR)
    n_fft = 2 ** int(np.ceil(np.log2(len(ir))))
    fr = np.fft.rfft(ir, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1 / fs)
    mag_db = 20 * np.log10(np.abs(fr) + 1e-12)

    with ir_plot_container:
        fig_ir_fr = ir_plot_container.figure
        fig_ir_fr.clear()
        fig_ir_fr.set_layout_engine('constrained')

        # IR Plot
        ax1 = fig_ir_fr.add_subplot(2, 1, 1)
        ax1.plot(time_axis, ir_zoom)
        ax1.set_title(f'Impulse Response (Zoomed): {latest_file.name}')
        ax1.set_xlabel('Time (ms)')
        ax1.set_ylabel('Amplitude')
        ax1.grid(True, alpha=0.3)

        # FR Plot
        ax2 = fig_ir_fr.add_subplot(2, 1, 2)
        ax2.semilogx(freqs, mag_db)
        ax2.set_title('Frequency Response')
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Magnitude (dB)')
        ax2.set_xlim(20, 20000)
        ax2.set_ylim(-60, 10)
        ax2.grid(True, which='both', alpha=0.3)

        ir_plot_container.update()


async def watch_file(main_plot, ir_plot):
    """Watch for changes in measurement_positions.csv"""
    file_path = Path('measurement_positions.csv')
    last_mtime = 0

    while True:
        try:
            if file_path.exists():
                current_mtime = file_path.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    update_plot()
                    update_ir_fr_plots(ir_plot)
            await asyncio.sleep(1)  # Check every second
        except asyncio.CancelledError:
            # Gracefully exit when NiceGUI shuts down and cancels this task
            break
        except Exception as e:
            print(f"Error watching file: {e}")
            await asyncio.sleep(1)


if __name__ in {"__main__", "__mp_main__"}:
    parser = argparse.ArgumentParser(description='Near-field scanner UI')
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Path to the configuration file',
    )
    args = parser.parse_args()
    config_file = args.config

    setup_logging(config_file, project_name="HarmonicDrive")


    # In-memory log buffer for the UI
    class LogBuffer:
        def __init__(self, max_lines=2000):
            self.buffer = queue.Queue()
            self.max_lines = max_lines

        def write(self, message):
            # Loguru sends the message as a string (including newline)
            self.buffer.put(message.strip())


    log_handler = LogBuffer()
    logger.add(log_handler.write, level="INFO",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")

    scanner = ScannerFactory.create(config_file)
    nfs = NearFieldScannerFactory.create(scanner, config_file)

    greyable_buttons = []


    def add_jog_row(axis: str, left_label: str, right_label: str, unit: str,
                    left_moves: list, right_moves: list):
        """Create a row like: [AXIS+UNIT] [120][60][10][1] [STOP] [1][10][60][120]. STOP triggers HOLD."""
        with ui.column().classes('w-full'):
            with ui.element('div').classes('jog-grid'):
                ui.label('')  # spacer (aligns with axis+unit cell below)
                ui.label(left_label).classes('jog-hdr jog-hdr-left')
                ui.label('STOP').classes('jog-hdr jog-hdr-stop')
                ui.label(right_label).classes('jog-hdr jog-hdr-right')

            with ui.element('div').classes('jog-grid'):
                ui.html(f'<div class="jog-axis">{axis}:<div class="jog-unit">{unit}</div></div>')

                # left side (big -> small); buttons show only numbers now
                for value, func in left_moves:
                    b = ui.button(
                        f'{value}',
                        on_click=log_button_click(f'{axis} {left_label} {value}{unit}',
                                                  lambda v=value, f=func: safe_move(f, v)),
                    ).classes('jog-btn')
                    greyable_buttons.append(b)

                # STOP button: HOLD only (do NOT disable; should work even during measurements)
                ui.button(
                    'STOP',
                    color='red',
                    on_click=log_button_click(f'{axis} STOP (HOLD)', lambda: run.io_bound(hold_scanner)),
                ).classes('jog-stop')

                # right side (small -> big); buttons show only numbers now
                for value, func in right_moves:
                    b = ui.button(
                        f'{value}',
                        on_click=log_button_click(f'{axis} {right_label} {value}{unit}',
                                                  lambda v=value, f=func: safe_move(f, v)),
                    ).classes('jog-btn')
                    greyable_buttons.append(b)


    # Plot axis limits
    AXIS_LIMIT = 400


    def _scanner_has_alarm() -> bool:
        """Alarm is active when GrblMachineState == ALARM."""
        try:
            st = scanner.get_state()
            if st is None:
                return False
            name = getattr(st, 'name', str(st))
            return str(name).upper() == 'ALARM'
        except Exception:
            return False


    def _is_home_successful() -> bool:
        """Homing is considered successful if we're not in ALARM."""
        return not _scanner_has_alarm()


    def _set_home_button_color(color: str) -> None:
        """Update HOME button color (NiceGUI Quasar color names: 'orange', 'green', etc.)."""
        try:
            home_button.props(f'color={color}')
        except Exception:
            pass


    # Whole app layout: left = controls + dials + plot, right = IR/FR plots
    # Logging is now in a separate toggleable dialog
    log_dialog = ui.dialog().props('full-width')
    with log_dialog, ui.card().classes('w-full flex flex-col').style(
            'height: 80vh; resize: both; overflow: auto; min-height: 400px;'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label('System Log').classes('text-xl font-bold')
            ui.button(icon='close', on_click=log_dialog.close).props('flat')
        log_view = ui.log(max_lines=2000).classes('w-full flex-1 overflow-auto border rounded p-2').style(
            'white-space: pre')

    with ui.splitter(value=50).classes('w-full h-screen items-stretch') as splitter:
        with splitter.before:
            with ui.column().classes('w-full h-full min-w-0 overflow-auto px-2 py-2'):

                # --- Jog rows (match the reference image layout) ---
                add_jog_row(
                    axis='PHI',
                    left_label='CW',
                    right_label='CCW',
                    unit='Deg',
                    left_moves=[(120, scanner.rotate_cw), (60, scanner.rotate_cw), (10, scanner.rotate_cw),
                                (1, scanner.rotate_cw)],
                    right_moves=[(1, scanner.rotate_ccw), (10, scanner.rotate_ccw), (60, scanner.rotate_ccw),
                                 (120, scanner.rotate_ccw)],
                )

                add_jog_row(
                    axis='R',
                    left_label='IN',
                    right_label='OUT',
                    unit='mm',
                    left_moves=[(120, scanner.move_in), (60, scanner.move_in), (10, scanner.move_in),
                                (1, scanner.move_in)],
                    right_moves=[(1, scanner.move_out), (10, scanner.move_out), (60, scanner.move_out),
                                 (120, scanner.move_out)],
                )

                add_jog_row(
                    axis='Z',
                    left_label='DOWN',
                    right_label='UP',
                    unit='mm',
                    left_moves=[(120, scanner.move_down), (60, scanner.move_down), (10, scanner.move_down),
                                (1, scanner.move_down)],
                    right_moves=[(1, scanner.move_up), (10, scanner.move_up), (60, scanner.move_up),
                                 (120, scanner.move_up)],
                )

                home_state = {'ok': False}  # startup: NOT homed => HOME stays orange until successful homing


                async def _wait_for_home_settle(timeout_s: float = 5.0) -> bool:
                    """Wait a short time after homing for the controller to settle; succeed if not in ALARM."""
                    deadline = time.time() + timeout_s
                    while time.time() < deadline:
                        if _scanner_has_alarm():
                            return False
                        try:
                            if scanner.get_position() is not None:
                                return True
                        except Exception:
                            pass
                        await asyncio.sleep(0.1)
                    return not _scanner_has_alarm()


                async def home_and_update():
                    # Run homing, then mark OK if we are not in ALARM after a brief settle period.
                    await safe_move(scanner.home)
                    home_state['ok'] = await _wait_for_home_settle()
                    _set_home_button_color('green' if home_state['ok'] else 'orange')


                # --- HOME / Clear Alarm / Soft Reset / REHOME row (like image) ---
                with ui.element('div').classes('cmd-row w-full justify-start mt-1'):
                    home_button = ui.button(
                        'HOME',
                        color='orange',  # startup: orange
                        on_click=log_button_click('Home', home_and_update),
                    ).classes('cmd-btn')

                    ui.button(
                        'Clear\nAlarm',
                        on_click=log_button_click('Clear Alarm', lambda: run.io_bound(scanner.clear_alarm)),
                    ).classes('cmd-btn cmd-btn-blue')

                    ui.button(
                        'Soft\nReset',
                        on_click=log_button_click('Soft Reset', lambda: run.io_bound(scanner.softreset)),
                    ).classes('cmd-btn cmd-btn-blue')

                    ui.button(
                        'REHOME',
                        on_click=log_button_click('ReHome', lambda: safe_move(rehome)),
                    ).classes('cmd-btn cmd-btn-blue')

                    ui.button(
                        'HOLD',
                        color='red',
                        on_click=log_button_click('Hold', lambda: run.io_bound(scanner.hold)),
                    ).classes('cmd-btn')

                with ui.button_group():
                    height_input = ui.number(label='Height Offset (mm)', value=0, format='%.2f')
                    ui.button(
                        'Set height offset',
                        on_click=log_button_click(
                            'Set height offset',
                            lambda: run.io_bound(scanner.set_speaker_center_above_stool, height_input.value),
                        ),
                    )

                greyable_buttons.append(
                    ui.button(
                        'Zero NFS',
                        color='orange',
                        on_click=log_button_click(
                            'Zero NFS',
                            lambda: zero_nfs_then_apply_height_offset(height_input.value),
                        ),
                    )
                )

                with ui.button_group():
                    greyable_buttons.append(
                        ui.button('Start measurements', on_click=log_button_click('Start measurements', async_task)))
                    greyable_buttons.append(ui.button('Take single measurement',
                                                      on_click=log_button_click('Take single measurement',
                                                                                async_single_measurement_task)))

                # --- Start/Stop NFS moved to the bottom of the button stack ---
                with ui.button_group().classes('mt-1'):
                    ui.button('Start NFS', color='green', on_click=log_button_click('Start NFS', start_nfs))
                    ui.button('Stop NFS', color='red', on_click=log_button_click('Stop NFS', stop_nfs))
                    ui.button('Show Logs', icon='list', on_click=log_dialog.open).classes('ml-2')

                with ui.row().classes('w-full justify-start items-center gap-4'):
                    # position_label = ui.label('Position: —') # Replaced with individual axis labels
                    with ui.row().classes('gap-4 items-center'):
                        # 7-segment style display: Share Tech Mono font, high contrast
                        card_classes = 'p-2 items-center bg-black rounded-lg border-2 border-gray-700 w-48'
                        label_classes = 'text-xs font-bold text-gray-300 uppercase tracking-widest mb-1'

                        # Background "inactive" segments effect: use absolute positioning to layer them
                        bg_value_classes = 'text-4xl font-bold text-[#1a3300] absolute'
                        value_classes = 'text-4xl font-bold text-[#7eff00] relative'
                        value_style = "font-family: 'Share Tech Mono', monospace; white-space: pre;"
                        unit_classes = 'text-xs font-bold text-gray-400 mt-1'

                        with ui.card().classes(card_classes):
                            ui.label('R (Radius)').classes(label_classes)
                            with ui.element('div').classes('relative'):
                                ui.label(' 888.88').classes(bg_value_classes).style(value_style)
                                pos_r = ui.label(' 000.00').classes(value_classes).style(value_style)
                            ui.label('mm').classes(unit_classes)
                        with ui.card().classes(card_classes):
                            ui.label('T (Theta)').classes(label_classes)
                            with ui.element('div').classes('relative'):
                                ui.label(' 888.88').classes(bg_value_classes).style(value_style)
                                pos_t = ui.label(' 000.00').classes(value_classes).style(value_style)
                            ui.label('°').classes(unit_classes)
                        with ui.card().classes(card_classes):
                            ui.label('Z (Height)').classes(label_classes)
                            with ui.element('div').classes('relative'):
                                ui.label(' 888.88').classes(bg_value_classes).style(value_style)
                                pos_z = ui.label(' 000.00').classes(value_classes).style(value_style)
                            ui.label('mm').classes(unit_classes)

                        with ui.card().classes(card_classes):
                            ui.label('Status').classes(label_classes)
                            with ui.element('div').classes('relative'):
                                ui.label('XXXXXXXX').classes(bg_value_classes).style(value_style)
                                pos_state = ui.label('   —   ').classes(value_classes).style(value_style)
                            ui.label('Mode').classes(unit_classes)

                plot = ui.matplotlib(figsize=(16, 7)).classes('w-full flex-1')
                with plot.figure as fig:
                    update_plot()

        with splitter.after:
            with ui.column().classes('w-full h-full min-w-0 flex flex-col p-2'):
                ui.label('Acoustic Analysis').classes('text-xl font-bold mb-1')
                ir_fr_plot = ui.matplotlib(figsize=(16, 12)).classes('w-full flex-1')
                with ir_fr_plot.figure as fig_ir_fr:
                    # Initial empty plots or load latest on start
                    pass

                ui.button('Refresh Plots', icon='refresh', on_click=lambda: update_ir_fr_plots(ir_fr_plot)).classes(
                    'mt-2')


                def tail_scanner_log():
                    if log_handler is None:
                        return
                    try:
                        while not log_handler.buffer.empty():
                            line = log_handler.buffer.get_nowait()
                            log_view.push(line)
                    except Exception as e:
                        log_view.push(f'[buffer error] {e}')


                ui.timer(0.5, tail_scanner_log)


    def _get_raw_state_string():
        """scanner.get_state() returns a GrblMachineState enum; show its raw string."""
        try:
            st = scanner.get_state()
            if st is None:
                return None
            # Return only the enum name (e.g., 'IDLE' instead of 'GrblStateMachine.IDLE')
            if hasattr(st, 'name'):
                return st.name
            return str(st).split('.')[-1]
        except Exception:
            return None


    def update_scanner_position(pos=None, state=None):
        def do_update():
            nonlocal pos, state
            if pos is None:
                pos = scanner.get_position()
            if pos is not None:
                pos_r.set_text(f'{pos.r():7.2f}')
                pos_t.set_text(f'{pos.t():7.2f}')
                pos_z.set_text(f'{pos.z():7.2f}')
            else:
                pos_r.set_text('   —   ')
                pos_t.set_text('   —   ')
                pos_z.set_text('   —   ')

            if state is None:
                raw_state = _get_raw_state_string()
            else:
                raw_state = state.name if hasattr(state, 'name') else str(state).split('.')[-1]

            if raw_state is not None:
                pos_state.set_text(f'{raw_state:^8}')
            else:
                pos_state.set_text('   —   ')

            # Update state text color and handle alarm logic: flash red and blink in ALARM, turn green otherwise
            if _scanner_has_alarm():
                # Change the large state text to red and add the flashing animation
                pos_state.classes(remove='text-[#7eff00]').classes(add='text-red-600 alarm_blink')

                # During/after alarm: HOME must be orange until a successful home is performed
                home_state['ok'] = False
                _set_home_button_color('orange')
            else:
                # Reset to the original green color when not in alarm
                pos_state.classes(remove='text-red-600 alarm_blink').classes(add='text-[#7eff00]')

                _set_home_button_color('green' if home_state['ok'] else 'orange')

        # Schedule the update on the main event loop to be thread-safe
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(do_update)
            else:
                do_update()
        except RuntimeError:
            do_update()


    scanner.set_on_state_update_callback(update_scanner_position)

    # Note: Using ui.timer instead of a raw background loop so it shuts down cleanly with NiceGUI
    ui.timer(1.0, lambda: watch_file(plot, ir_fr_plot))

    # Start measurements if nfs exists
    if nfs:
        update_ir_fr_plots(ir_fr_plot)

    ui.run(reload=False)
