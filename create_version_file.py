# create_version_file.py
import pyinstaller_versionfile

pyinstaller_versionfile.create_versionfile(
    output_file="version.txt",
    version="1.0.0.0",
    company_name="Joral LLC",
    file_description="Rotary Encoder Visualizer",
    internal_name="EncoderVisualizer",
    legal_copyright="© Joral LLC. All rights reserved.",
    original_filename="EncoderVisualizer.exe",
    product_name="Encoder Visualizer"
)