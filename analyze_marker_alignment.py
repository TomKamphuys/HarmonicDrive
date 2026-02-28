import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def analyze_alignment():
    filepath = Path("./Recordings/debug/alignment_debug.npz")
    
    if not filepath.exists():
        print(f"Error: Could not find {filepath}. Make sure you ran a sweep with debug_saves=True.")
        return

    # Load data
    data = np.load(filepath)
    x = data['x']
    ref = data['ref']
    lags = data['lags']
    corr = data['corr']
    peak_idx = int(data['peak_idx'])
    match_pct = float(data['match_pct'])

    print("=== Alignment Analysis ===")
    print(f"Detected Lag (T0): {peak_idx} samples")
    print(f"Match Quality:     {match_pct * 100:.2f}%")

    # Set up the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.canvas.manager.set_window_title("Barker Marker Alignment Analysis")

    # --- Plot 1: Cross-Correlation Function ---
    ax1.set_title(f"Cross-Correlation (Match Quality: {match_pct * 100:.1f}%)")
    ax1.plot(lags, corr, color='tab:blue', label="Correlation")
    ax1.axvline(peak_idx, color='red', linestyle='--', label=f"Peak at {peak_idx}")
    
    # Zoom in around the peak for the x-axis
    zoom_window = len(ref) * 2
    ax1.set_xlim(peak_idx - zoom_window, peak_idx + zoom_window)
    ax1.set_xlabel("Lag (Samples)")
    ax1.set_ylabel("Correlation Amplitude")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # --- Plot 2: Time-Domain Overlay ---
    ax2.set_title("Time-Domain Overlay (Reference vs. Shifted Loopback)")
    
    # Align the loopback recording to the reference
    if peak_idx >= 0:
        aligned_x = x[peak_idx : peak_idx + len(ref)]
    else:
        # If lag is negative, pad the loopback
        aligned_x = np.pad(x, (abs(peak_idx), 0))[:len(ref)]
    
    # Pad to match reference length if it was cut short at the end of the buffer
    if len(aligned_x) < len(ref):
        aligned_x = np.pad(aligned_x, (0, len(ref) - len(aligned_x)))

    # Normalize both for visual comparison
    ref_norm = ref / (np.max(np.abs(ref)) + 1e-12)
    x_norm = aligned_x / (np.max(np.abs(aligned_x)) + 1e-12)

    time_axis = np.arange(len(ref))
    ax2.plot(time_axis, ref_norm, color='black', linewidth=2, label="Digital Reference")
    ax2.plot(time_axis, x_norm, color='tab:orange', alpha=0.8, label="Recorded Loopback")
    
    ax2.set_xlabel("Samples")
    ax2.set_ylabel("Normalized Amplitude")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    analyze_alignment()