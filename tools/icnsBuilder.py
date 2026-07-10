import shutil
import subprocess
import os


def pngtoico(png, output_dir="./assets/icons/mac/"):
    # Prepare paths
    iconset = f"{os.path.splitext(os.path.split(png)[1])[0]}.iconset"

    iconset_dir = os.path.join(output_dir, iconset)
    sizes = [(16, 16), (32, 32), (32, 32), (64, 64), (128, 128), (256, 256), (256, 256), (512, 512), (512, 512)]
    output_files = [
        "icon_16x16.png",
        "icon_16x16@2x.png",
        "icon_32x32.png",
        "icon_32x32@2x.png",
        "icon_128x128.png",
        "icon_128x128@2x.png",
        "icon_256x256.png",
        "icon_256x256@2x.png",
        "icon_512x512.png",
    ]

    os.makedirs(iconset_dir, exist_ok=True)

    for (width, height), output_file in zip(sizes, output_files):
        command = ["sips", "-z", str(width), str(height), png, "--out", os.path.join(iconset_dir, output_file)]
        subprocess.run(command, check=True)

    shutil.copy(png, os.path.join(iconset_dir, "icon_512x512@2x.png"))
    iconutil_command = ["iconutil", "-c", "icns", iconset_dir]
    subprocess.run(iconutil_command, check=True)

    shutil.rmtree(iconset_dir)


if __name__ == "__main__":
    pngtoico("./assets/icons/mac/icon.png")
    pngtoico("./assets/icons/mac/icoDMG.png")
