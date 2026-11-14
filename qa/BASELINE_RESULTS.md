# Detector baseline results

The original v0.2 detector was exercised on Linux/Python 3.13.5/NumPy 2.3.5: 71 unit checks, 360 clean images, 240 degraded images and 144 invalid images. All final checks passed. Clean-suite maximum angular error was about 0.68 degrees and its 95th percentile about 0.28 degrees; the degraded suite's maximum was about 0.45 degrees. The case sets differ.

An earlier run found that a clipped ring could be accepted as a smaller ellipse. The detector was corrected and the final invalid-image suite rejected all 144 cases. Initial failures are historical development results, not final-code results.

The sample is one development image without independently measured azimuth. Its approximate regression output is center (53.73,54.06) in the crop, image bisector 297.97 degrees, and 757 classified pixels.

These are image-geometry results. They do not establish live capture, hotkey behavior, slope correction, or actual game-bearing accuracy. Review the exact commit's Actions results for additional executed checks. Reproduce all case-level outputs with tools/run_matrix.py into a fresh output directory.
