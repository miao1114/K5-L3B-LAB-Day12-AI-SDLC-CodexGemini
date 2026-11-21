# Benchmark environment

Windows-11-10.0.26200-SP0

Chrome/Chromium 157.0.8103.80, headless with real Canvas.
Viewport 1280x720, DPR 1; CSS canvas [672, 378], backing canvas [672, 378].
Core Gather simulation; assets/player/fish/crocodile confirmed through actual drawImage calls.
load_ms: Python monotonic before startup until browser acknowledges first completed ready scene frame.
Includes readiness polling overhead; no clock-domain subtraction. Warm-up >=3 seconds.
Frame times: consecutive completed draw calls, anchor and all samples inside measurement.
One screenshot during measurement may introduce an honest outlier. No effects disabled.
