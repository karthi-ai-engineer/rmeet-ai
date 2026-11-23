# Max film (84 s, 1920×1080, 30 fps)

Script and storyboard: `docs/video/max-film-script.md`. Output: `video/out/Max-film.mp4` (not in git).

| Step | Command (from the repo root) |
|---|---|
| Voices (local Kokoro on :8400, free) | `.venv-tts\Scripts\python video\scripts\make_vo.py` |
| Preview in a browser (space = play) | open `video/film/index.html` (add `?t=37` to jump) |
| Review stills | `cd video; node render.mjs --stills 3,21,37` → `out/stills/` |
| Render the picture | `cd video; node render.mjs` → `out/video.mp4` (+ `out/timeline.json`) |
| Sound + final film | `.venv-tts\Scripts\python video\scripts\build_audio.py` → `out/mix.wav`, `out/Max-film.mp4` |

- The film is a web page whose every frame is a pure function of time (`film/film.js`, `renderAt(t)`), rendered frame
  by frame with headless Chromium (Playwright) and encoded with ffmpeg (`winget install Gyan.FFmpeg`). No screen
  recording, so every render is identical.
- UI sounds are generated in code; voices are Kokoro (Apache-2.0); music: see `assets/music/LICENSE.md`.
- First full render: 2,520 frames in 21 min (CPU: PNG frames + x264 slow). Speed-ups planned: GPU drawing in Chrome,
  JPEG frames, NVENC for drafts.
