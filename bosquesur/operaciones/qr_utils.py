"""Utilidad para generar códigos QR en SVG sin depender de internet."""
import io

import qrcode
import qrcode.image.svg


def generar_qr_svg(contenido: str) -> str:
    """Devuelve un SVG inline limpio del código QR para etiquetas físicas y vistas web/móvil."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")
