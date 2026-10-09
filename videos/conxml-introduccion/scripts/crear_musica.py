"""Pista instrumental original de ConXml. Síntesis determinista; sin samples externos."""
from pathlib import Path
import wave
import numpy as np

RATE = 48000
DURATION = 18
N = RATE * DURATION
mix = np.zeros((N, 2), dtype=np.float64)

def add(signal, start, pan=0):
    first = int(start * RATE)
    count = min(len(signal), N - first)
    if count <= 0:
        return
    theta = (pan + 1) * np.pi / 4
    mix[first:first + count, 0] += signal[:count] * np.cos(theta)
    mix[first:first + count, 1] += signal[:count] * np.sin(theta)

def freq(midi):
    return 440 * 2 ** ((midi - 69) / 12)

def key(midi, duration=2.8, level=.12):
    t = np.arange(int(duration * RATE)) / RATE
    f = freq(midi)
    # Timbre de piano eléctrico cálido, con parciales que decaen por separado.
    voice = (np.sin(2 * np.pi * f * t) * np.exp(-t / 1.25)
        + .25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / .65)
        + .07 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t / .28))
    env = (1 - np.exp(-t / .018)) * np.minimum(1, (duration - t) / .3)
    return level * voice * env

def pad(midi, duration=3.8, level=.017):
    t = np.arange(int(duration * RATE)) / RATE
    f = freq(midi)
    voice = np.sin(2 * np.pi * f * t) + .18 * np.sin(2 * np.pi * 2 * f * t)
    env = np.minimum(1, t / .7) * np.minimum(1, (duration - t) / 1.1)
    return level * voice * env

# Seis compases, 80 BPM. Cmaj9 → Am7 → Fmaj7 → Gsus2 → Am7 → Cmaj9.
chords = [[48, 55, 59, 62, 64], [45, 52, 55, 60, 64],
          [41, 48, 52, 57, 60], [43, 50, 57, 62, 67],
          [45, 52, 55, 60, 64], [48, 55, 59, 62, 64]]
for bar, notes in enumerate(chords):
    start = bar * 3
    for j, midi in enumerate(notes):
        add(pad(midi), start, -.3 + .15 * j)
    # Arpegio pausado: deja espacio visual para leer las instrucciones.
    pattern = [notes[1] + 12, notes[2] + 12, notes[3] + 12, notes[2] + 12]
    for j, midi in enumerate(pattern):
        add(key(midi, level=.105 if j == 0 else .085), start + .18 + j * .75,
            -.18 if j % 2 == 0 else .18)
    add(key(notes[0], duration=3.1, level=.065), start + .05)

# Reverberación breve y discreta, con retardos fijos y sin bucles.
dry = mix.copy()
for delay, gain in [(.081,.075),(.143,.06),(.237,.045),(.383,.025)]:
    offset = int(delay * RATE)
    mix[offset:] += dry[:-offset, ::-1] * gain
# Una envolvente de seguridad microscópica evita clics; los fades se editan en Studio.
ramp = int(.02 * RATE)
mix[:ramp] *= np.linspace(0,1,ramp)[:,None]
mix[-ramp:] *= np.linspace(1,0,ramp)[:,None]
peak = np.max(np.abs(mix))
mix *= .23 / max(peak,1e-9)
out = Path(__file__).resolve().parents[1] / 'assets/audio/conxml-bienvenida.wav'
with wave.open(str(out), 'wb') as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(RATE)
    f.writeframes((mix * 32767).astype('<i2').tobytes())
print(f'Pista original: {DURATION}s, estéreo, {RATE}Hz; pico -12.8 dBFS.')
