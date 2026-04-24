"""
QR code generation and decoding for Keystone UR strings.
"""

import io
import os
from pathlib import Path

PENDING_DIR = Path.home() / ".exme" / "pending"


def generate_qr(ur_string: str, output_path: str = None) -> str:
    """Generate QR code PNG from UR string. Returns file path."""
    import qrcode

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = str(PENDING_DIR / "sign_request.png")

    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(ur_string.upper())  # UR strings are case-insensitive, uppercase is smaller QR
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)

    return output_path


def decode_qr_from_image(image_path: str) -> str:
    """Decode QR code from photo/screenshot -> UR string."""
    from pyzbar import pyzbar
    from PIL import Image

    img = Image.open(image_path)
    decoded = pyzbar.decode(img)

    if not decoded:
        raise ValueError(f"No QR code found in {image_path}")

    # Return first detected QR data
    data = decoded[0].data.decode("utf-8")
    return data.lower()  # UR strings are case-insensitive
