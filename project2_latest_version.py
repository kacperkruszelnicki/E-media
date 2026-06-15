from PIL import Image
from Crypto.Util.number import getPrime, inverse, bytes_to_long, long_to_bytes
import zlib
import struct
import binascii
import random
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Cipher import PKCS1_OAEP
import math
import numpy as np

# RSA
def generate_keys(bits=1024):
    p = getPrime(bits)
    q = getPrime(bits)

    while q == p:
        q = getPrime(bits)

    n = p * q
    phi = (p - 1) * (q - 1)

    e = 65537
    while phi % e == 0:
        e += 2

    d = inverse(e, phi)

    return (e, n), (d, n)

def rsa_encrypt(m, e, n):
    return pow(m, e, n)

def rsa_decrypt(c, d, n):
    return pow(c, d, n)

# PARAMETRY
BLOCK_SIZE = 100  # Można modyfikować rozmiar bloku

# DYNAMICZNE OBLICZANIE
def cipher_block_size(n):
    return (n.bit_length() + 7) // 8


# ECB
def encrypt_ecb(data, public_key):
    e, n = public_key

    original_length = len(data)#

    out = bytearray()

    # zapis długości danych
    out.extend(
        original_length.to_bytes(8, "big")
    )

    for i in range(0, len(data), BLOCK_SIZE):

        block = data[i:i + BLOCK_SIZE]

        if len(block) < BLOCK_SIZE:
            block += b'\x00' * (BLOCK_SIZE - len(block))

        m = bytes_to_long(block)

        c = rsa_encrypt(m, e, n)

        cipher_size = cipher_block_size(n)

        out.extend(
            c.to_bytes(cipher_size, "big")
        )
    return bytes(out)


def decrypt_ecb(data, private_key):
    d, n = private_key

    # odczyt długości
    original_length = int.from_bytes(
        data[:8],
        "big"
    )

    out = bytearray()

    cipher_size = cipher_block_size(n)

    for i in range(8, len(data), cipher_size):
        c = int.from_bytes(data[i:i + cipher_size], "big")

        m = rsa_decrypt(c, d, n)

        out.extend(long_to_bytes(m, BLOCK_SIZE))

    return bytes(out[:original_length])

# CBC
def encrypt_cbc(data, public_key):

    e, n = public_key

    cipher_size = cipher_block_size(n)

    original_length = len(data)

    out = bytearray()

    # zapis długości danych
    out.extend(
        original_length.to_bytes(8, "big")
    )

    # losowy IV
    prev = random.getrandbits(
        BLOCK_SIZE * 8
    )

    # zapis IV
    out.extend(
        prev.to_bytes(BLOCK_SIZE, "big")
    )

    mask = (1 << (BLOCK_SIZE * 8)) - 1

    for i in range(0, len(data), BLOCK_SIZE):

        block = data[i:i + BLOCK_SIZE]

        if len(block) < BLOCK_SIZE:
            block += b"\x00" * (
                BLOCK_SIZE - len(block)
            )

        m = bytes_to_long(block)

        # CBC XOR
        m ^= prev

        c = rsa_encrypt(m, e, n)

        out.extend(
            c.to_bytes(cipher_size, "big")
        )

        # następny blok CBC
        prev = c & mask

    return bytes(out)


def decrypt_cbc(data, private_key):

    d, n = private_key

    cipher_size = cipher_block_size(n)

    # odczyt długości
    original_length = int.from_bytes(
        data[:8],
        "big"
    )

    # odczyt IV
    prev = int.from_bytes(
        data[8:8 + BLOCK_SIZE],
        "big"
    )

    mask = (1 << (BLOCK_SIZE * 8)) - 1

    out = bytearray()

    start = 8 + BLOCK_SIZE

    for i in range(
        start,
        len(data),
        cipher_size
    ):

        c = int.from_bytes(
            data[i:i + cipher_size],
            "big"
        )

        m = rsa_decrypt(c, d, n)

        m ^= prev

        out.extend(
            long_to_bytes(
                m,
                BLOCK_SIZE
            )
        )

        prev = c & mask

    return bytes(out[:original_length])

# PNG HANDLING
PNG_SIG = b'\x89PNG\r\n\x1a\n'

def parse_chunks(data):
    chunks = []
    i = 8

    while i < len(data):

        length = struct.unpack(">I", data[i:i+4])[0]
        ctype = data[i+4:i+8]
        cdata = data[i+8:i+8+length]
        crc = data[i+8+length:i+12+length]

        chunks.append((ctype, cdata))

        i += length + 12

    return chunks


def make_chunk(ctype, cdata):
    crc = binascii.crc32(ctype + cdata) & 0xffffffff

    return (
        struct.pack(">I", len(cdata)) +
        ctype +
        cdata +
        struct.pack(">I", crc)
    )

# Dodawanie i usuwanie filtrów w png
def get_png_info(chunks):
    for ctype, cdata in chunks:
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", cdata)
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 3)
            bpp = max(1, (bit_depth * channels) // 8)
            return width, height, bpp
    return 0, 0, 0

def remove_png_filters(data, width, height, bpp):
    row_size = width * bpp
    out = bytearray()
    prev_row = bytearray(row_size)
    i = 0

    for y in range(height):
        if i >= len(data): break
        ftype = data[i]
        i += 1
        row = bytearray(data[i : i + row_size])
        i += row_size
        recon = bytearray(row_size)

        for x in range(row_size):
            a = recon[x - bpp] if x >= bpp else 0
            b = prev_row[x]
            c = prev_row[x - bpp] if x >= bpp else 0

            if ftype == 0: val = row[x]
            elif ftype == 1: val = row[x] + a
            elif ftype == 2: val = row[x] + b
            elif ftype == 3: val = row[x] + (a + b) // 2
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                val = row[x] + pr
            else: val = row[x]

            recon[x] = val & 0xff

        out.extend(recon)
        prev_row = recon
    return bytes(out)

def add_png_filters_none(data, width, bpp):
    row_size = width * bpp
    out = bytearray()
    for i in range(0, len(data), row_size):
        chunk = data[i : i + row_size]
        if not chunk: break
        out.append(0)  # Dodawanie filtru "0" (None) na początek każdej linii
        out.extend(chunk)
    return bytes(out)

def strip_none_filters(data, width, bpp):
    row_size = width * bpp + 1
    out = bytearray()
    for i in range(0, len(data), row_size):
        out.extend(data[i+1 : i+row_size])
    return bytes(out)

# PNG ENCRYPT / DECRYPT
def update_ihdr_height(cdata, new_height):
    # IHDR składa się z 13 bajtów: szerokość(4), wysokość(4), bit_depth(1), color_type(1), compression(1), filter(1), interlace(1)
    width = struct.unpack(">I", cdata[:4])[0]
    tail = cdata[8:] # pozostałe flagi
    return struct.pack(">I", width) + struct.pack(">I", new_height) + tail

def encrypt_png(path_in, path_out, key, mode="ECB", decompress=True):
    raw = open(path_in, "rb").read()
    chunks = parse_chunks(raw)
    width, height, bpp = get_png_info(chunks)

    idat = bytearray()
    others = []
    for ctype, cdata in chunks:
        if ctype == b"IDAT": idat.extend(cdata)
        else: others.append((ctype, cdata))

    if decompress:
        decompressed_data = zlib.decompress(idat)
        data = remove_png_filters(decompressed_data, width, height, bpp)
    else:
        data = idat

    # Szyfrowanie
    if mode == "ECB": enc = encrypt_ecb(data, key)
    else: enc = encrypt_cbc(data, key)

    if decompress:
        # Obliczanie nowej wysokości
        row_size = width * bpp
        new_height = math.ceil(len(enc) / row_size)
        
        # Dodawanie padding zerami
        needed_bytes = new_height * row_size
        enc += b'\x00' * (needed_bytes - len(enc))

        # Dodawanie pustych filtrów i kompresja
        enc = add_png_filters_none(enc, width, bpp)
        enc = zlib.compress(enc)

        # Modyfikowanie IHDR
        for i, (ctype, cdata) in enumerate(others):
            if ctype == b"IHDR":
                others[i] = (b"IHDR", update_ihdr_height(cdata, new_height))
    else:
        pass

    out = bytearray(PNG_SIG)
    inserted = False
    for ctype, cdata in others:
        if ctype == b"IEND" and not inserted:
            out.extend(make_chunk(b"IDAT", enc))
            inserted = True
        out.extend(make_chunk(ctype, cdata))

    open(path_out, "wb").write(out)
    print(f"Zapisano zaszyfrowany ({mode}, decomp={decompress}):", path_out)


def decrypt_png(path_in, path_out, key, mode="ECB", decompress=True):
    raw = open(path_in, "rb").read()
    chunks = parse_chunks(raw)
    width, height, bpp = get_png_info(chunks)

    idat = bytearray()
    others = []
    for ctype, cdata in chunks:
        if ctype == b"IDAT": idat.extend(cdata)
        else: others.append((ctype, cdata))

    if decompress:
        decompressed_data = zlib.decompress(idat)
        data = strip_none_filters(decompressed_data, width, bpp)
    else:
        data = idat

    # Deszyfrowanie
    if mode == "ECB": dec = decrypt_ecb(data, key)
    else: dec = decrypt_cbc(data, key)

    if decompress:
        # obliczanie oryginalnej wysokości
        row_size = width * bpp
        original_height = len(dec) // row_size

        dec = add_png_filters_none(dec, width, bpp)
        dec = zlib.compress(dec)

        # Przywracanie oryginalnej wysokości w IHDR
        for i, (ctype, cdata) in enumerate(others):
            if ctype == b"IHDR":
                others[i] = (b"IHDR", update_ihdr_height(cdata, original_height))

    out = bytearray(PNG_SIG)
    inserted = False
    for ctype, cdata in others:
        if ctype == b"IEND" and not inserted:
            out.extend(make_chunk(b"IDAT", dec))
            inserted = True
        out.extend(make_chunk(ctype, cdata))

    open(path_out, "wb").write(out)
    print(f"Zapisano odszyfrowany ({mode}, decomp={decompress}):", path_out)

    # BIBLIOTECZNE RSA
def library_rsa_png_demo(input_png):

    print("\n=== BIBLIOTECZNE RSA PKCS#1 v1.5 ===")

    img = Image.open(input_png)

    mode = img.mode
    size = img.size
    pixels = img.tobytes()

    print("Tryb:", mode)
    print("Rozmiar:", size)
    print("Liczba bajtów:", len(pixels))

    # Klucz podobnego rzędu wielkości jak ręczny
    rsa_key = RSA.generate(2048)

    cipher_enc = PKCS1_v1_5.new(rsa_key.publickey())
    cipher_dec = PKCS1_v1_5.new(rsa_key)

    key_bytes = rsa_key.size_in_bytes()

    # PKCS#1 v1.5 wymaga 11 bajtów narzutu
    BLOCK = key_bytes - 11

    print("Rozmiar klucza:", rsa_key.size_in_bits(), "bitów")
    print("Maksymalny blok danych:", BLOCK, "bajtów")

    encrypted_blocks = []

    for i in range(0, len(pixels), BLOCK):

        block = pixels[i:i + BLOCK]

        encrypted_blocks.append(
            cipher_enc.encrypt(block)
        )

    ciphertext = b"".join(encrypted_blocks)

    print("Liczba bloków:", len(encrypted_blocks))
    print("Rozmiar szyfrogramu:", len(ciphertext))

    # zapis obrazu szyfrogramu

    width = size[0]

    height = math.ceil(
        len(ciphertext) / (3 * width)
    )

    needed = width * height * 3

    padded = ciphertext + b"\x00" * (
        needed - len(ciphertext)
    )

    cipher_img = Image.frombytes(
        "RGB",
        (width, height),
        padded
    )

    cipher_img.save("pkcs1_cipher.png")

    print("Zapisano: pkcs1_cipher.png")

    # odszyfrowanie

    recovered = bytearray()

    sentinel = b"ERROR"

    for block in encrypted_blocks:

        dec = cipher_dec.decrypt(block, sentinel)

        if dec == sentinel:
            raise ValueError(
                "Błąd odszyfrowania PKCS#1 v1.5"
            )

        recovered.extend(dec)

    recovered = recovered[:len(pixels)]

    restored = Image.frombytes(
        mode,
        size,
        bytes(recovered)
    )

    restored.save("pkcs1_reconstructed.png")

    print("Zapisano: pkcs1_reconstructed.png")

    print(
        "Czy odzyskano oryginał:",
        bytes(recovered) == pixels
    )


if __name__ == "__main__":

    INPUT = "image.png"

    Image.open(INPUT).verify()

    public, private = generate_keys(1024)

    print("Public:", public)
    print("Private:", private)

    encrypt_png(INPUT, "ecb.png", public, "ECB", True)
    encrypt_png(INPUT, "cbc.png", public, "CBC", True)

    decrypt_png("ecb.png", "ecb_dec.png", private, "ECB", True)
    decrypt_png("cbc.png", "cbc_dec.png", private, "CBC", True)

    encrypt_png(INPUT, "ecb_raw.png", public, "ECB", False)
    encrypt_png(INPUT, "cbc_raw.png", public, "CBC", False)

    decrypt_png("ecb_raw.png", "ecb_raw_dec.png", private, "ECB", False)
    decrypt_png("cbc_raw.png", "cbc_raw_dec.png", private, "CBC", False)

    # TEST BIBLIOTECZNEGO RSA
    library_rsa_png_demo(INPUT)
