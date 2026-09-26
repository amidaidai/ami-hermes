---
name: songsee
category: community
description: Audio spectrogram analysis — mel spectrogram, chroma, MFCC features via CLI. (moved from media)
---

# Songsee — Audio Spectrogram Analysis

Analyze audio files by extracting spectrogram features — mel spectrograms, chroma features, MFCCs — directly from the CLI.

## When to use

- You need to inspect the frequency structure of an audio file
- You want to extract feature vectors for classification or similarity
- You're building audio pipelines and need quick feature extraction

## Requirements

- Python with `librosa`, `numpy`, `matplotlib`
- FFmpeg installed on the system
- Input audio files in common formats (MP3, WAV, FLAC, OGG)

## Usage

### Extract mel spectrogram

```bash
python -c "
import librosa, numpy as np
y, sr = librosa.load('input.wav', sr=None)
mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
mel_db = librosa.power_to_db(mel, ref=np.max)
print(f'Mel spectrogram shape: {mel_db.shape}')
print(f'Range: {mel_db.min():.1f} to {mel_db.max():.1f} dB')
"
```

### Extract MFCC features

```bash
python -c "
import librosa, numpy as np
y, sr = librosa.load('input.wav', sr=None)
mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
print(f'MFCC shape: {mfccs.shape}')
print(f'Mean MFCCs: {np.mean(mfccs, axis=1)}')
"
```

### Extract chroma features

```bash
python -c "
import librosa, numpy as np
y, sr = librosa.load('input.wav', sr=None)
chroma = librosa.feature.chroma_stft(y=y, sr=sr)
print(f'Chroma shape: {chroma.shape}')
print(f'Chroma mean per pitch class: {np.mean(chroma, axis=1)}')
"
```

### Save spectrogram as image

```bash
python -c "
import librosa, matplotlib.pyplot as plt
y, sr = librosa.load('input.wav', sr=None)
mel = librosa.feature.melspectrogram(y=y, sr=sr)
mel_db = librosa.power_to_db(mel, ref=mel.max())
plt.figure(figsize=(10,4))
librosa.display.specshow(mel_db, sr=sr, x_axis='time', y_axis='mel')
plt.colorbar(format='%+2.0f dB')
plt.title('Mel spectrogram')
plt.tight_layout()
plt.savefig('spectrogram.png', dpi=150)
print('Saved spectrogram.png')
"
```

## Pitfalls

- `librosa.load` can be slow on large files — trim or downsample first if you only need a segment
- Default sample rate (22050 Hz) may lose high frequencies — pass `sr=None` to preserve original
- Feature vectors from different sample rates aren't directly comparable — always note the sr
- Ensure FFmpeg is in PATH or librosa will fail on compressed formats

## Verification

Run a quick test on a known file and check that the output shapes match expectations:
- Mel spectrogram of a 10s file at sr=22050, hop_length=512 → ~862 time frames × 128 mel bins
