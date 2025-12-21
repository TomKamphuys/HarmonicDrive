from nicegui import app, ui, run  # Add 'app' to your imports
import numpy as np
import asyncio
import time
from pathlib import Path

from nfs import NearFieldScannerFactory, ScannerFactory

def start_nfs():
    pass

def stop_nfs():
    print('Stopping NFS')
    # Use a try-except here just in case nfs isn't fully initialized
    try:
        nfs.shutdown()
    except Exception as e:
        print(f"Error during shutdown: {e}")

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


async def safe_move(func, *args):
    """Wrapper to disable UI, run a hardware command, then re-enable UI"""
    for button in greyable_buttons:
        button.disable()
    try:
        await run.io_bound(func, *args)
    finally:
        for button in greyable_buttons:
            button.enable()


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
    config_file = './config.ini'
    scanner = ScannerFactory.create(config_file)
    nfs = NearFieldScannerFactory.create(scanner, config_file)

    greyable_buttons = []

    # Plot axis limits
    AXIS_LIMIT = 400

    with ui.button_group():
        greyable_buttons.append(ui.button(' 1 degree  CCW', on_click=lambda: safe_move(scanner.rotate_ccw, 1)))
        greyable_buttons.append(ui.button('10 degrees CCW', on_click=lambda: safe_move(scanner.rotate_ccw, 10)))
        greyable_buttons.append(ui.button(' 1 degree  CW', on_click=lambda: safe_move(scanner.rotate_cw, 1)))
        greyable_buttons.append(ui.button('10 degrees CW', on_click=lambda: safe_move(scanner.rotate_cw, 10)))

    with ui.button_group():
        greyable_buttons.append(ui.button('In  1mm', on_click=lambda: safe_move(scanner.move_in, 1)))
        greyable_buttons.append(ui.button('In 10mm', on_click=lambda: safe_move(scanner.move_in, 10)))
        greyable_buttons.append(ui.button('Out  1mm', on_click=lambda: safe_move(scanner.move_out, 1)))
        greyable_buttons.append(ui.button('Out 10mm', on_click=lambda: safe_move(scanner.move_out, 10)))

    with ui.button_group():
        greyable_buttons.append(ui.button('Up  1mm', on_click=lambda: safe_move(scanner.move_up, 1)))
        greyable_buttons.append(ui.button('Up 10mm', on_click=lambda: safe_move(scanner.move_up, 10)))
        greyable_buttons.append(ui.button('Down  1mm', on_click=lambda: safe_move(scanner.move_down, 1)))
        greyable_buttons.append(ui.button('Down 10mm', on_click=lambda: safe_move(scanner.move_down, 10)))

    with ui.button_group():
        ui.button('Start NFS', color='green', on_click=start_nfs)
        ui.button('Stop NFS', color='red', on_click=stop_nfs)
        ui.button('Home', on_click=lambda: safe_move(scanner.home))
        ui.button('Clear Alarm', on_click=lambda: run.io_bound(scanner.clear_alarm))
        ui.button('Soft Reset', on_click=lambda: run.io_bound(scanner.softreset))
        ui.button('ReHome', on_click=lambda: safe_move(rehome))

    with ui.button_group():
        ui.button('TEST: go to stool position', on_click=lambda: safe_move(DEMO_move_to_stool))
        ui.button('Set stool reference', on_click=lambda: scanner.set_stool_reference)
        height_input = ui.number(label='Height Offset (mm)', value=0, format='%.2f')
        ui.button('Set height offset', on_click=lambda: scanner.set_height_offset(height_input.value))
        ui.button('Switch to WCS', on_click=lambda: scanner.set_working_coordinate_system)

    with ui.button():
        greyable_buttons.append(ui.button('Zero NFS', color='orange', on_click=scanner.set_as_zero))


    with ui.button():
        ui.button('Start measurements', on_click=async_task)

    with ui.row().classes('w-full justify-center items-center gap-12'):
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
                        {'from': -360, 'to': -300, 'color': '#ff4d4d'}, # Danger zone
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

    position_label = ui.label()

    def update_scanner_position():
        pos = scanner.get_position()
        if pos is not None:
            position_label.set_text(f'Position: {pos}')

            # Update Rotation Gauge
            gauge_rot.options['series'][0]['data'] = [pos.t()]
            gauge_rot.update()

            # Update In/Out Bar
            gauge_inout.options['series'][0]['data'] = [pos.r()]
            gauge_inout.update()

            # Update Up/Down Column
            gauge_updown.options['series'][0]['data'] = [pos.z()]
            gauge_updown.update()
        else:
            position_label.set_text('No position available')


    ui.timer(0.5, update_scanner_position)


    plot = ui.matplotlib(figsize=(8, 6))
    with plot.figure as fig:
        update_plot()


    # Start watching the file for changes
    ui.timer(1.0, update_plot)


    ui.run(reload=False)
