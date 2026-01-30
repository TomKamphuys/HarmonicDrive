from nicegui import app, ui, run  # Add 'app' to your imports
import argparse
import numpy as np
import asyncio
import time
from pathlib import Path

from loguru import logger

from nfs import NearFieldScannerFactory, ScannerFactory

# --- Loguru: write UI click logs to the same scanner.log file (append) ---
logger.remove()  # avoid duplicate console handlers if any
logger.add(
    "scanner.log",
    level="INFO",
    encoding="utf-8",
    enqueue=True,           # thread/process-safe-ish; good with UI + io_bound
    backtrace=False,
    diagnose=False,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
)

def log_button_click(label: str, handler):
    """Wrap a NiceGUI on_click handler to log the click and then run it (sync or async)."""
    async def _wrapped(*args, **kwargs):
        logger.info("UI click: {}", label)
        result = handler(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return _wrapped

# Flashing animation for ALARM indicator
ui.add_css("""
@keyframes alarm_blink {
  0%   { opacity: 1; }
  50%  { opacity: 0.15; }
  100% { opacity: 1; }
}
.alarm_blink {
  animation: alarm_blink 0.6s linear infinite;
}
""")

def start_nfs():
    pass

def stop_nfs():
    print('Stopping NFS')
    # Use a try-except here just in case nfs isn't fully initialized
    try:
        nfs.shutdown()
    except Exception as e:
        print(f"Error during shutdown: {e}")

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
    nfs.take_measurement_set()

async def async_task():
    ui.notify('Measurement started')
    for button in greyable_buttons:
        button.disable()

    try:
        # run.io_bound keeps the UI responsive/connected
        await run.io_bound(nfs.take_measurement_set)
    finally:
        # Use finally to ensure buttons re-enable even if the task fails
        ui.notify('Measurement finished')
        for button in greyable_buttons:
            button.enable()

async def async_single_measurement_task():
    ui.notify('Single measurement started')
    for button in greyable_buttons:
        button.disable()

    try:
        await run.io_bound(nfs.take_single_measurement)
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
    """Load cylindrical coordinates from measurement_positions.txt and convert to azimuth/elevation"""
    file_path = Path('measurement_positions.txt')
    if not file_path.exists():
        return None, None
    
    try:
        data = np.loadtxt(file_path, delimiter=',', skiprows=1)
        if data.size == 0:
            return None, None
        
        r = data[:, 0]
        theta = data[:, 1]  # This is azimuth (theta)
        z = data[:, 2]
        
        # Calculate elevation angle from cylindrical coordinates
        # elevation = arctan(z / r)
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


async def watch_file():
    """Watch for changes in measurement_positions.txt"""
    file_path = Path('measurement_positions.txt')
    last_mtime = 0

    while True:
        try:
            if file_path.exists():
                current_mtime = file_path.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    update_plot()
        except Exception as e:
            print(f"Error watching file: {e}")

        await asyncio.sleep(1)  # Check every second


if __name__ in {"__main__", "__mp_main__"}:
    parser = argparse.ArgumentParser(description='Near-field scanner UI')
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Path to the configuration file',
    )
    args = parser.parse_args()
    config_file = args.config
    scanner = ScannerFactory.create(config_file)
    nfs = NearFieldScannerFactory.create(scanner, config_file)

    greyable_buttons = []

    # Plot axis limits
    AXIS_LIMIT = 400

    # Whole app layout: left = controls + dials + plot, right = log (user-resizable)
    with ui.splitter(value=50).classes('w-full h-screen items-stretch') as splitter:
        with splitter.before:
            with ui.column().classes('w-full h-full min-w-0 overflow-auto'):
                with ui.button_group():
                    greyable_buttons.append(ui.button(' 1 degree  CCW', on_click=log_button_click('1 degree CCW', lambda: safe_move(scanner.rotate_ccw, 1))))
                    greyable_buttons.append(ui.button('10 degrees CCW', on_click=log_button_click('10 degrees CCW', lambda: safe_move(scanner.rotate_ccw, 10))))
                    greyable_buttons.append(ui.button(' 1 degree  CW', on_click=log_button_click('1 degree CW', lambda: safe_move(scanner.rotate_cw, 1))))
                    greyable_buttons.append(ui.button('10 degrees CW', on_click=log_button_click('10 degrees CW', lambda: safe_move(scanner.rotate_cw, 10))))

                with ui.button_group():
                    greyable_buttons.append(ui.button('In  1mm', on_click=log_button_click('In 1mm', lambda: safe_move(scanner.move_in, 1))))
                    greyable_buttons.append(ui.button('In 10mm', on_click=log_button_click('In 10mm', lambda: safe_move(scanner.move_in, 10))))
                    greyable_buttons.append(ui.button('Out  1mm', on_click=log_button_click('Out 1mm', lambda: safe_move(scanner.move_out, 1))))
                    greyable_buttons.append(ui.button('Out 10mm', on_click=log_button_click('Out 10mm', lambda: safe_move(scanner.move_out, 10))))

                with ui.button_group():
                    greyable_buttons.append(ui.button('Up  1mm', on_click=log_button_click('Up 1mm', lambda: safe_move(scanner.move_up, 1))))
                    greyable_buttons.append(ui.button('Up 10mm', on_click=log_button_click('Up 10mm', lambda: safe_move(scanner.move_up, 10))))
                    greyable_buttons.append(ui.button('Down  1mm', on_click=log_button_click('Down 1mm', lambda: safe_move(scanner.move_down, 1))))
                    greyable_buttons.append(ui.button('Down 10mm', on_click=log_button_click('Down 10mm', lambda: safe_move(scanner.move_down, 10))))

                with ui.button_group():
                    ui.button('Start NFS', color='green', on_click=log_button_click('Start NFS', start_nfs))
                    ui.button('Stop NFS', color='red', on_click=log_button_click('Stop NFS', stop_nfs))
                    ui.button('Home', on_click=log_button_click('Home', lambda: safe_move(scanner.home)))
                    ui.button('Clear Alarm', on_click=log_button_click('Clear Alarm', lambda: run.io_bound(scanner.clear_alarm)))
                    ui.button('Soft Reset', on_click=log_button_click('Soft Reset', lambda: run.io_bound(scanner.softreset)))
                    ui.button('ReHome', on_click=log_button_click('ReHome', lambda: safe_move(rehome)))

                with ui.button_group():
                    height_input = ui.number(label='Height Offset (mm)', value=0, format='%.2f')
                    ui.button(
                        'Set height offset',
                        on_click=log_button_click(
                            'Set height offset',
                            lambda: run.io_bound(scanner.set_speaker_center_above_stool, height_input.value),
                        ),
                    )

                # FIX: don't nest a button inside another button (that causes overlap)
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
                    greyable_buttons.append(ui.button('Start measurements', on_click=log_button_click('Start measurements', async_task)))
                    greyable_buttons.append(ui.button('Take single measurement', on_click=log_button_click('Take single measurement', async_single_measurement_task)))

                with ui.row().classes('w-full justify-start items-center gap-12'):
                    # --- ROTATION GAUGE ---
                    with ui.column().classes('items-center'):
                        ui.label('Rotation (deg)').classes('font-bold')
                        gauge_rot = ui.highchart({
                            'chart': {'type': 'gauge', 'height': 200, 'width': 200, 'backgroundColor': 'transparent'},
                            'title': None,
                            'pane': {'startAngle': -150, 'endAngle': 150, 'background': {'backgroundColor': '#f5f5f5', 'innerRadius': '60%', 'outerRadius': '100%', 'shape': 'arc'}},
                            'yAxis': {
                                'min': -360, 'max': 360,
                                'minorTickInterval': 'auto', 'tickPixelInterval': 30,
                                'plotBands': [
                                    {'from': -360, 'to': -300, 'color': '#ff4d4d'},  # Danger zone
                                    {'from': 300, 'to': 360, 'color': '#ff4d4d'}
                                ],
                                'title': {'text': '°'}
                            },
                            'series': [{'name': 'Rotation', 'data': [0], 'tooltip': {'valueSuffix': ' deg'}}]
                        }, extras=['highcharts-more'])

                    # --- IN/OUT INDICATOR (Horizontal Linear) ---
                    with ui.column().classes('items-center'):
                        ui.label('In/Out (mm)').classes('font-bold')
                        gauge_inout = ui.highchart({
                            'chart': {'type': 'bar', 'height': 120, 'width': 300, 'backgroundColor': 'transparent'},
                            'title': None,
                            'xAxis': {'categories': ['In/Out'], 'visible': False},
                            'yAxis': {
                                'min': -800, 'max': 800,
                                'title': {'text': 'Distance (mm)'},
                                'plotBands': [{'from': -800, 'to': 800, 'color': '#eeeeee'}]
                            },
                            'legend': {'enabled': False},
                            'series': [{'name': 'Position', 'data': [0], 'color': '#2196f3'}]
                        })

                    # --- UP/DOWN INDICATOR (Vertical Linear) ---
                    with ui.column().classes('items-center'):
                        ui.label('Up/Down (mm)').classes('font-bold')
                        gauge_updown = ui.highchart({
                            'chart': {'type': 'column', 'height': 300, 'width': 120, 'backgroundColor': 'transparent'},
                            'title': None,
                            'xAxis': {'categories': ['Up/Down'], 'visible': False},
                            'yAxis': {
                                'min': -800, 'max': 800,
                                'title': {'text': 'Height (mm)'},
                                'plotBands': [{'from': -800, 'to': 800, 'color': '#eeeeee'}]
                            },
                            'legend': {'enabled': False},
                            'series': [{'name': 'Position', 'data': [0], 'color': '#9c27b0'}]
                        })

                with ui.row().classes('w-full justify-start items-center gap-8'):
                    alarm_badge = ui.badge('ALARM').props('color=red outline')
                    alarm_badge.visible = False  # off until alarm happens

                    position_label = ui.label('Position: —')
                    state_label = ui.label('State: —')

                plot = ui.matplotlib(figsize=(8, 6))
                with plot.figure as fig:
                    update_plot()

        with splitter.after:
            with ui.column().classes('w-full h-full min-w-0 flex flex-col'):
                ui.label('Log (tail)').classes('font-bold')
                log_view = ui.log(max_lines=2000).classes('w-full flex-1 overflow-auto')
                log_view.set_visibility(True)

                log_file = Path('scanner.log')
                _log_tail_state = {'pos': 0}

                def tail_scanner_log():
                    try:
                        if not log_file.exists():
                            return

                        size = log_file.stat().st_size
                        if size < _log_tail_state['pos']:
                            # log rotated/truncated
                            _log_tail_state['pos'] = 0

                        with log_file.open('r', encoding='utf-8', errors='replace') as f:
                            f.seek(_log_tail_state['pos'])
                            chunk = f.read()
                            _log_tail_state['pos'] = f.tell()

                        if not chunk:
                            return

                        for line in chunk.splitlines():
                            log_view.push(line)
                    except Exception as e:
                        log_view.push(f'[tail error] {e}')

                ui.timer(0.5, tail_scanner_log)

    def _get_raw_state_string():
        """scanner.get_state() returns a GrblMachineState enum; show its raw string."""
        try:
            st = scanner.get_state()
            return None if st is None else str(st)
        except Exception:
            return None

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

    def update_scanner_position():
        pos = scanner.get_position()
        if pos is not None:
            position_label.set_text(f'Position: {pos}')

            # We call the chart's update method directly.
            # This performs a "soft" update of the data points.
            gauge_rot.run_method('update', {'series': [{'data': [pos.t()]}]})
            gauge_inout.run_method('update', {'series': [{'data': [pos.r()]}]})
            gauge_updown.run_method('update', {'series': [{'data': [pos.z()]}]})
        else:
            position_label.set_text('Position: (no position available)')

        raw_state = _get_raw_state_string()
        if raw_state is not None:
            state_label.set_text(f'State: {raw_state}')
        else:
            state_label.set_text('State: (unavailable)')

        # Alarm indicator: flash red in ALARM, turn off otherwise
        if _scanner_has_alarm():
            alarm_badge.visible = True
            alarm_badge.classes(add='alarm_blink')
        else:
            alarm_badge.visible = False
            alarm_badge.classes(remove='alarm_blink')

    ui.timer(0.5, update_scanner_position)

    # Start watching the file for changes
    ui.timer(1.0, update_plot)

    ui.run(reload=False)
