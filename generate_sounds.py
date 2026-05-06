import wave
import struct
import math
import os

def generate_wav(filename, notes, duration_per_note=0.15, volume=0.5, sample_rate=44100):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for freq in notes:
            num_samples = int(duration_per_note * sample_rate)
            for i in range(num_samples):
                # Apply envelope (fade out)
                envelope = math.exp(-3 * i / num_samples)
                value = int(volume * envelope * 32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate))
                data = struct.pack('<h', value)
                wav_file.writeframesraw(data)

# Frequencies for notes
C5 = 523.25
E5 = 659.25
G5 = 783.99
C6 = 1046.50

# 1. Soft Bell (A single resonant chime)
generate_wav("alertas/soft_bell.wav", [G5], duration_per_note=1.5)

# 2. Success Chime (Classic ascending arpeggio)
generate_wav("alertas/success_chime.wav", [C5, E5, G5, C6], duration_per_note=0.15)

# 3. Arcade Level Up (Fast, energetic)
generate_wav("alertas/arcade_level_up.wav", [C5, G5, E5, C6, G5, E5, C6, C6], duration_per_note=0.08)

print("Sounds generated in alertas/ folder.")
