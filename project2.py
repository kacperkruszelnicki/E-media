from PIL import Image
from Crypto.Util.number import getPrime, inverse, bytes_to_long, long_to_bytes
import zlib
import struct
import binascii
import random
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import math


# RSA

def generate_keys(bits=16):
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

BLOCK_SIZE = 2  # 16-bit blocks


# ECB

def encrypt_ecb(data, public_key):
    e, n = public_key

    out = bytearray()

    for i in range(0, len(data), BLOCK_SIZE):

        block = data[i:i + BLOCK_SIZE]

        if len(block) < BLOCK_SIZE:
            block += b'\x00'

        m = bytes_to_long(block)

        c = rsa_encrypt(m, e, n)

        out.extend(c.to_bytes(4, "big"))

    return bytes(out)


def decrypt_ecb(data, private_key):
    d, n = private_key

    out = bytearray()

    for i in range(0, len(data), 4):

        c = int.from_bytes(data[i:i + 4], "big")

        m = rsa_decrypt(c, d, n)

        out.extend(long_to_bytes(m, BLOCK_SIZE))

    return bytes(out)


# CBC

def encrypt_cbc(data, public_key):
    e, n = public_key

    out = bytearray()

    prev = random.randint(0, 65535)

    out.extend(prev.to_bytes(2, "big"))#

    for i in range(0, len(data), BLOCK_SIZE):

        block = data[i:i + BLOCK_SIZE]

        if len(block) < BLOCK_SIZE:
            block += b'\x00'

        m = bytes_to_long(block)

        m = m ^ prev

        c = rsa_encrypt(m, e, n)

        out.extend(c.to_bytes(4, "big"))

        prev = c % 65536

    return bytes(out)


def decrypt_cbc(data, private_key):
    d, n = private_key

    prev = int.from_bytes(data[:2], "big")

    out = bytearray()

    for i in range(2, len(data), 4):

        c = int.from_bytes(data[i:i + 4], "big")

        m = rsa_decrypt(c, d, n)

        m = m ^ prev

        out.extend(long_to_bytes(m, BLOCK_SIZE))

        prev = c % 65536

    return bytes(out)


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


# PNG ENCRYPT / DECRYPT

def encrypt_png(path_in, path_out, key, mode="ECB", decompress=True):

    raw = open(path_in, "rb").read()
    chunks = parse_chunks(raw)

    idat = bytearray()
    others = []

    for ctype, cdata in chunks:
        if ctype == b"IDAT":
            idat.extend(cdata)
        else:
            others.append((ctype, cdata))

    if decompress:
        data = zlib.decompress(idat)
        print("IDAT compressed:", len(idat))
        print("After decompress:", len(data))
    else:
        data = idat

    if mode == "ECB":
        enc = encrypt_ecb(data, key)
    else:
        enc = encrypt_cbc(data, key)

    if decompress:
        enc = zlib.compress(enc)

    out = bytearray(PNG_SIG)

    inserted = False

    for ctype, cdata in others:

        if ctype == b"IEND" and not inserted:
            out.extend(make_chunk(b"IDAT", enc))
            inserted = True

        out.extend(make_chunk(ctype, cdata))

    open(path_out, "wb").write(out)

    print("Zapisano:", path_out)


def decrypt_png(path_in, path_out, key, mode="ECB", decompress=True):

    raw = open(path_in, "rb").read()
    chunks = parse_chunks(raw)

    idat = bytearray()
    others = []

    for ctype, cdata in chunks:
        if ctype == b"IDAT":
            idat.extend(cdata)
        else:
            others.append((ctype, cdata))

    if decompress:
        data = zlib.decompress(idat)
    else:
        data = idat

    if mode == "ECB":
        dec = decrypt_ecb(data, key)
    else:
        dec = decrypt_cbc(data, key)

    if decompress:
        dec = zlib.compress(dec)

    out = bytearray(PNG_SIG)

    inserted = False

    for ctype, cdata in others:

        if ctype == b"IEND" and not inserted:
            out.extend(make_chunk(b"IDAT", dec))
            inserted = True

        out.extend(make_chunk(ctype, cdata))

    open(path_out, "wb").write(out)

    print("Zapisano:", path_out)

# LIBRARY RSA (OAEP)

def library_rsa_png_demo(input_png):

    print("\n=== BIBLIOTECZNE RSA OAEP ===")

    img = Image.open(input_png)

    mode = img.mode
    size = img.size
    pixels = img.tobytes()

    print("Tryb:", mode)
    print("Rozmiar:", size)
    print("Liczba bajtów:", len(pixels))

    # OAEP wymaga dużego klucza
    rsa_key = RSA.generate(1024)

    cipher_enc = PKCS1_OAEP.new(rsa_key.publickey())
    cipher_dec = PKCS1_OAEP.new(rsa_key)

    # dla RSA-1024 bezpieczny rozmiar bloku
    BLOCK = 80

    blocks = []

    for i in range(0, len(pixels), BLOCK):
        blocks.append(
            pixels[i:i + BLOCK]
        )

    print("Liczba bloków:", len(blocks))

    encrypted_blocks = []

    for block in blocks:
        encrypted_blocks.append(
            cipher_enc.encrypt(block)
        )

    ciphertext = b"".join(encrypted_blocks)

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

    cipher_img.save("oaep_cipher.png")

    print("Zapisano: oaep_cipher.png")

    # odszyfrowanie

    recovered = bytearray()

    for block in encrypted_blocks:

        recovered.extend(
            cipher_dec.decrypt(block)
        )

    recovered = recovered[:len(pixels)]

    restored = Image.frombytes(
        mode,
        size,
        bytes(recovered)
    )

    restored.save("oaep_reconstructed.png")

    print("Zapisano: oaep_reconstructed.png")

    print(
        "Czy odzyskano oryginał:",
        bytes(recovered) == pixels
    )

# MAIN

if __name__ == "__main__":

    INPUT = "image.png"

    Image.open(INPUT).verify()

    public, private = generate_keys(16)

    print("Public:", public)
    print("Private:", private)

    encrypt_png(INPUT, "ecb.png", public, "ECB", True)
    encrypt_png(INPUT, "cbc.png", public, "CBC", True)

    decrypt_png("ecb.png", "ecb_dec.png", private, "ECB", True)
    decrypt_png("cbc.png", "cbc_dec.png", private, "CBC", True)

    encrypt_png(INPUT, "ecb_raw.png", public, "ECB", False)
    encrypt_png(INPUT, "cbc_raw.png", public, "CBC", False)

    # TEST BIBLIOTECZNEGO RSA

    library_rsa_png_demo(INPUT)
