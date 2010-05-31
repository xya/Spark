import sys
from cx_Freeze import setup, Executable

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(name="Spark",
    version="0.0.4",
    description="Simple file-transfer application",
    executables=[Executable("../../src/spark/start_gui.py", 
                    base=base, 
                    targetName="Spark.exe")])
