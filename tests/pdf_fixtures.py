def make_valid_pdf() -> bytes:
    """Создаёт минимальный настоящий PDF с одной страницей."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 300 144] "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    content = b"BT /F1 12 Tf 20 100 Td (Test PDF) Tj ET"
    objects.append(
        b"<< /Length " + str(len(content)).encode() +
        b" >>\nstream\n" + content + b"\nendstream"
    )

    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for number, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(
            f"{number} 0 obj\n".encode() +
            obj +
            b"\nendobj\n"
        )

    xref_offset = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    result.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())

    result.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )

    return bytes(result)