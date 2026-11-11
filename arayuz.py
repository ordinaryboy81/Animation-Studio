# Animation Studio 1.2.x and older start this file. The studio itself is studio.py.
# Kept so that older launchers and the 1.2 updater keep working; you can ignore it.
import os, runpy, sys

yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio.py")
sys.argv[0] = yol
runpy.run_path(yol, run_name="__main__")
