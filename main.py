from nicegui import ui, run
import numpy as np
import asyncio
from pathlib import Path
import time

from nfs import NearFieldScannerFactory, ScannerFactory, NearFieldScanner

def start_nfs():
    pass


def stop_nfs():
    print('Stopping NFS')
    nfs.shutdown()

async def take_measurement():
    nfs.take_measurement_set()


async def async_task():
    ui.notify('Measurement started')
    for button in greyable_buttons:
        button.disable()

    await run.io_bound(nfs.take_measurement_set)

    ui.notify('Measurement finished')
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
        greyable_buttons.append(ui.button(' 1 degree  CCW', on_click=lambda: scanner.rotate_ccw(1)))
        greyable_buttons.append(ui.button('10 degrees CCW', on_click=lambda: scanner.rotate_ccw(10)))
        greyable_buttons.append(ui.button(' 1 degree  CW', on_click=lambda: scanner.rotate_cw(1)))
        greyable_buttons.append(ui.button('10 degrees CW', on_click=lambda: scanner.rotate_cw(10)))

    with ui.button_group():
        greyable_buttons.append(ui.button('In  1mm', on_click=lambda: scanner.move_in(1)))
        greyable_buttons.append(ui.button('In 10mm', on_click=lambda: scanner.move_in(10)))
        greyable_buttons.append(ui.button('Out  1mm', on_click=lambda: scanner.move_out(1)))
        greyable_buttons.append(ui.button('Out 10mm', on_click=lambda: scanner.move_out(10)))

    with ui.button_group():
        greyable_buttons.append(ui.button('Up  1mm', on_click=lambda: scanner.move_up(1)))
        greyable_buttons.append(ui.button('Up 10mm', on_click=lambda: scanner.move_up(10)))
        greyable_buttons.append(ui.button('Down  1mm', on_click=lambda: scanner.move_down(1)))
        greyable_buttons.append(ui.button('Down 10mm', on_click=lambda: scanner.move_down(10)))


    with ui.button():
        ui.button('Start NFS', color='green', on_click=start_nfs)
        ui.button('Stop NFS', color='red', on_click=stop_nfs)


    with ui.button():
        greyable_buttons.append(ui.button('Zero NFS', color='orange', on_click=scanner.set_as_zero))


    with ui.button():
        ui.button('Start measurements', on_click=async_task)


    plot = ui.matplotlib(figsize=(8, 6))
    with plot.figure as fig:
        update_plot()


    # Start watching the file for changes
    ui.timer(1.0, update_plot)


    ui.run(reload=False)
