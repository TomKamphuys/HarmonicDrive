import soundfile as sf
from pathlib import Path

def audit_recordings(base_path="./Recordings"):
    """Scans for WAV files and prints embedded RIFF INFO metadata."""
    path = Path(base_path)
    
    # Define directories to scan
    dirs_to_scan = [path, path / "debug"]
    
    print(f"{'FILENAME':<45} | {'TITLE':<35} | {'COMMENT'}")
    print("-" * 110)

    for target_dir in dirs_to_scan:
        if not target_dir.exists():
            continue
            
        # Only look for .wav files
        for wav_file in target_dir.glob("*.wav"):
            try:
                with sf.SoundFile(str(wav_file)) as f:
                    # Accessing the property-based metadata attributes
                    title = f.title if f.title else "None"
                    comment = f.comment if f.comment else "None"
                    
                    # Truncate filename for display if too long
                    fname = wav_file.name if len(wav_file.name) < 45 else f"...{wav_file.name[-42:]}"
                    print(f"{fname:<45} | {title:<35} | {comment}")
            except Exception as e:
                print(f"Could not read {wav_file.name}: {e}")

if __name__ == "__main__":
    audit_recordings()