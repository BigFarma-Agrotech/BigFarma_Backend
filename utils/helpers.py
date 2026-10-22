import random
import string

def generate_otp_code(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))

def split_images(raw) -> list:
    """Split a product's comma-joined images column back into a list.

    Images are stored joined with ",", but base64 data URLs contain a comma
    themselves ("data:image/png;base64,iVBOR..."), so a plain split cuts every
    data URL in two. Re-attach each "data:...;base64" header to its payload.
    """
    if not raw:
        return []
    images = []
    parts = [part.strip() for part in raw.split(',')]
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.startswith('data:') and part.endswith(';base64') and i + 1 < len(parts):
            images.append(f"{part},{parts[i + 1]}")
            i += 2
            continue
        if part:
            images.append(part)
        i += 1
    return images