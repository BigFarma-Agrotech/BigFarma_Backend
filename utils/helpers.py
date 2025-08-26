import random
import string

def generate_otp_code(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))