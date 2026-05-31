import cv2
import numpy as np
from matplotlib import pyplot as plt
import struct
from PIL import Image, PngImagePlugin
import zlib

def append_secret_data(file_path, secret_message):
    # Przekształcanie tekstu na bajty
    data_to_hide = secret_message.encode('utf-8')
    
    with open(file_path, 'ab') as f:
        f.write(data_to_hide)
        
    print(f"Pomyślnie dopisano {len(data_to_hide)} bajtów za końcem pliku {file_path}.")

def convert_jpg_to_png_with_exif(jpg_path, png_path):
    # Otwórz plik JPG
    img = Image.open(jpg_path)

    # Kontener na metadane PNG
    meta = PngImagePlugin.PngInfo()
    
    # Kopiowanie metadanych tekstowych (jeśli istnieją w JPG)
    for key, value in img.info.items():
        if key != 'exif':
            meta.add_text(str(key), str(value))
    
    # Pobierz surowe dane EXIF (jeśli istnieją)
    exif_data = img.info.get('exif')
    
    if exif_data:
        # Zapisz jako PNG, przekazując pobrane dane EXIF
        img.save(png_path, format='PNG', exif=exif_data, pnginfo=meta)
        print(f"Konwersja zakończona. Dane EXIF i text zostały zachowane w {png_path}.")
    else:
        img.save(png_path, format='PNG')
        print("Plik JPG nie zawierał danych EXIF. Zapisano czysty plik PNG.")

def fourier_transform_rgb(image_path):
    # Wczytanie obrazu kolorowego (BGR)
    img_bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)

    if img_bgr is None:
        print("Błąd: Nie można odnaleźć pliku lub plik jest uszkodzony.")
        return

    # Konwersja BGR -> RGB
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Konwersja do float64 dla większej dokładności
    img = np.float64(img)

    # Rozdzielenie kanałów RGB
    r = img[:, :, 0]
    g = img[:, :, 1]
    b = img[:, :, 2]

    # Transformata Fouriera
    dft_r = np.fft.fft2(r)
    dft_g = np.fft.fft2(g)
    dft_b = np.fft.fft2(b)

    # Centrowanie widma
    dft_shift_r = np.fft.fftshift(dft_r)
    dft_shift_g = np.fft.fftshift(dft_g)
    dft_shift_b = np.fft.fftshift(dft_b)

    # Widmo amplitudowe
    magnitude_r = 20 * np.log(np.abs(dft_shift_r) + 1)
    magnitude_g = 20 * np.log(np.abs(dft_shift_g) + 1)
    magnitude_b = 20 * np.log(np.abs(dft_shift_b) + 1)

    # Połączenie widm w obraz RGB
    magnitude_rgb = np.stack(
        [magnitude_r, magnitude_g, magnitude_b],
        axis=2
    )

    # Normalizacja do zakresu 0-1 dla poprawnego wyświetlania
    magnitude_rgb = cv2.normalize(
        magnitude_rgb,
        None,
        0,
        1,
        cv2.NORM_MINMAX
    )

    # Widmo fazowe
    phase_r = np.angle(dft_shift_r)
    phase_g = np.angle(dft_shift_g)
    phase_b = np.angle(dft_shift_b)

    # Normalizacja fazy do zakresu 0-1
    phase_r = (phase_r + np.pi) / (2 * np.pi)
    phase_g = (phase_g + np.pi) / (2 * np.pi)
    phase_b = (phase_b + np.pi) / (2 * np.pi)

    phase_rgb = np.stack(
        [phase_r, phase_g, phase_b],
        axis=2
    )

    # Odwrotna transformata
    # Cofnięcie przesunięcia
    f_ishift_r = np.fft.ifftshift(dft_shift_r)
    f_ishift_g = np.fft.ifftshift(dft_shift_g)
    f_ishift_b = np.fft.ifftshift(dft_shift_b)

    # Odwrotna FFT
    img_back_r = np.fft.ifft2(f_ishift_r)
    img_back_g = np.fft.ifft2(f_ishift_g)
    img_back_b = np.fft.ifft2(f_ishift_b)

    # Pobranie części rzeczywistej
    img_back_r = np.real(img_back_r)
    img_back_g = np.real(img_back_g)
    img_back_b = np.real(img_back_b)

    # Połączenie kanałów
    img_back = np.stack(
        [img_back_r, img_back_g, img_back_b],
        axis=2
    )

    # Różnica obrazu
    difference = img - img_back

    # Statystyki błędu
    print(f"Suma wszystkich różnic: {np.sum(difference):.5e}")
    print(f"Maksymalna różnica w pojedynczym pikselu: "
          f"{np.max(np.abs(difference)):.5e}")

    # Wyświetlanie wyników
    plt.figure(figsize=(25, 5))

    # Oryginał
    plt.subplot(151)
    plt.imshow(np.uint8(img))
    plt.title('1. Oryginał RGB')
    plt.axis('off')

    # Widmo amplitudowe RGB
    plt.subplot(152)
    plt.imshow(magnitude_rgb)
    plt.title('2. Widmo amplitudowe RGB')
    plt.axis('off')

    # Widmo fazowe RGB
    plt.subplot(153)
    plt.imshow(phase_rgb)
    plt.title('3. Widmo fazowe RGB')
    plt.axis('off')

    # Rekonstrukcja
    plt.subplot(154)
    plt.imshow(np.uint8(np.clip(img_back, 0, 255)))
    plt.title('4. Rekonstrukcja')
    plt.axis('off')

    # Różnica
    plt.subplot(155)

    # Wzmocnienie różnic dla lepszej widoczności
    diff_display = difference.copy()

    # Normalizacja różnic do wyświetlenia
    diff_display = cv2.normalize(
        diff_display,
        None,
        0,
        1,
        cv2.NORM_MINMAX
    )

    plt.imshow(diff_display)
    plt.title('5. Różnica')
    plt.axis('off')

    plt.tight_layout()
    plt.show()

def fourier_transform(image_path):
    # Wczytanie obrazu w skali szarości
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    if img is None:
        print("Błąd: Nie można odnaleźć pliku lub plik jest uszkodzony.")
        return
    img = np.float32(img)
    # Transformata Fouriera 2D
    dft = np.fft.fft2(img)
    
    # Przesunięcie niskich częstotliwości do środka (centrowanie)
    dft_shift = np.fft.fftshift(dft)
    
    # Obliczenie Modułu (Spektrum Amplitudowe)
    magnitude_spectrum = 20 * np.log(np.abs(dft_shift) + 1)
    #magnitude_spectrum = 20 * np.log(np.abs(dft) + 1)###
    
    # Obliczenie Fazy
    phase_spectrum = np.angle(dft_shift)
    #phase_spectrum = np.angle(dft)###

    # Odwrotna transformata Fouriera
    
    # Cofnięcie przesunięcia
    f_ishift = np.fft.ifftshift(dft_shift)###
    
    # Odwrotna transformata
    img_back = np.fft.ifft2(f_ishift)###
    #img_back = np.fft.ifft2(dft)
    
    # Odtworzone wartości
    img_back = np.abs(img_back)

    # Różnica obrazu przed i po transformacie
    difference = img - img_back

    # Błąd rekonstrukcji obrazu
    print(f"Suma wszystkich różnic: {np.sum(difference):.5e}")
    print(f"Maksymalna różnica w pojedynczym pikselu: {np.max(np.abs(difference)):.5e}")

    # Prezentacja wyników
    plt.figure(figsize=(25, 5))

    plt.subplot(151)
    plt.imshow(img, cmap='gray')
    plt.title('1. Oryginał')
    plt.axis('off')

    plt.subplot(152)
    plt.imshow(magnitude_spectrum, cmap='magma')
    plt.title('2. Moduł (Widmo)')
    plt.axis('off')

    plt.subplot(153)
    plt.imshow(phase_spectrum, cmap='gray')
    plt.title('3. Faza')
    plt.axis('off')

    plt.subplot(154)
    plt.imshow(img_back, cmap='gray')
    plt.title('4. Rekonstrukcja po transformacie')
    plt.axis('off')

    plt.subplot(155)
    plt.imshow(difference, cmap='seismic')
    plt.title('5. Różnica przed i po transformacie')
    plt.axis('off')

    plt.tight_layout()
    plt.show()

EXIF_TAGS = {
    # --- IFD0 (podstawowe) ---
    0x010E: "ImageDescription",
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x0128: "ResolutionUnit",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x013E: "WhitePoint",
    0x013F: "PrimaryChromaticities",
    0x0213: "YCbCrPositioning",
    0x8298: "Copyright",

    # --- Wskaźniki ---
    0x8769: "ExifIFDPointer",
    0x8825: "GPSInfoIFDPointer",
    0xA005: "InteropIFDPointer",

    # --- ExifIFD ---
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8822: "ExposureProgram",
    0x8824: "SpectralSensitivity",
    0x8827: "ISO",
    0x8830: "SensitivityType",
    0x9000: "ExifVersion",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x9101: "ComponentsConfiguration",
    0x9102: "CompressedBitsPerPixel",
    0x9201: "ShutterSpeedValue",
    0x9202: "ApertureValue",
    0x9203: "BrightnessValue",
    0x9204: "ExposureBiasValue",
    0x9205: "MaxApertureValue",
    0x9206: "SubjectDistance",
    0x9207: "MeteringMode",
    0x9208: "LightSource",
    0x9209: "Flash",
    0x920A: "FocalLength",
    0x9214: "SubjectArea",

    # --- dodatkowe ---
    0x927C: "MakerNote",
    0x9286: "UserComment",
    0x9290: "SubSecTime",
    0x9291: "SubSecTimeOriginal",
    0x9292: "SubSecTimeDigitized",

    # --- obraz ---
    0xA000: "FlashpixVersion",
    0xA001: "ColorSpace",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
    0xA004: "RelatedSoundFile",

    # --- dodatkowe EXIF ---
    0xA20E: "FocalPlaneXResolution",
    0xA20F: "FocalPlaneYResolution",
    0xA210: "FocalPlaneResolutionUnit",
    0xA217: "SensingMethod",
    0xA300: "FileSource",
    0xA301: "SceneType",
    0xA401: "CustomRendered",
    0xA402: "ExposureMode",
    0xA403: "WhiteBalance",
    0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm",
    0xA406: "SceneCaptureType",
    0xA407: "GainControl",
    0xA408: "Contrast",
    0xA409: "Saturation",
    0xA40A: "Sharpness",
    0xA40C: "SubjectDistanceRange",

    # --- GPS ---
    0x0000: "GPSVersionID",
    0x0001: "GPSLatitudeRef",
    0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef",
    0x0004: "GPSLongitude",
    0x0005: "GPSAltitudeRef",
    0x0006: "GPSAltitude",
    0x0007: "GPSTimeStamp",
    0x000D: "GPSDateStamp",

    # --- Interop ---
    0x0001: "InteropIndex",
}

VALUE_MAPS = {

    "MeteringMode": {
        0: "Unknown",
        1: "Average",
        2: "Center-weighted average",
        3: "Spot",
        4: "Multi-spot",
        5: "Multi-segment",
        6: "Partial",
    },

    "ExposureProgram": {
        0: "Not defined",
        1: "Manual",
        2: "Normal program",
        3: "Aperture priority",
        4: "Shutter priority",
        5: "Creative program",
        6: "Action program",
        7: "Portrait mode",
        8: "Landscape mode",
    },

    "LightSource": {
        0: "Unknown",
        1: "Daylight",
        2: "Fluorescent",
        3: "Tungsten",
        4: "Flash",
        9: "Fine weather",
        10: "Cloudy",
        11: "Shade",
    },

    "Flash": {
        0: "Flash did not fire",
        1: "Flash fired",
        5: "Flash fired, return not detected",
        7: "Flash fired, return detected",
    },

    "WhiteBalance": {
        0: "Auto",
        1: "Manual",
    },

    "SceneCaptureType": {
        0: "Standard",
        1: "Landscape",
        2: "Portrait",
        3: "Night scene",
    },

    "ExposureMode": {
        0: "Auto",
        1: "Manual",
        2: "Auto bracket",
    },

    "GainControl": {
        0: "None",
        1: "Low gain up",
        2: "High gain up",
        3: "Low gain down",
        4: "High gain down",
    },

    "Contrast": {
        0: "Normal",
        1: "Soft",
        2: "Hard",
    },

    "Saturation": {
        0: "Normal",
        1: "Low",
        2: "High",
    },

    "Sharpness": {
        0: "Normal",
        1: "Soft",
        2: "Hard",
    },

    "SubjectDistanceRange": {
        0: "Unknown",
        1: "Macro",
        2: "Close",
        3: "Distant",
    }
}

def analyze_png_attributes(file_path):
    with open(file_path, 'rb') as f:
        signature = f.read(8)
        if signature != b'\x89PNG\r\n\x1a\n':
            print("To nie jest poprawny plik PNG!")
            return

        while True:
            # Odczyt długości danych (4 bajty)
            chunk_length_raw = f.read(4)
            if not chunk_length_raw:
                break  # Koniec pliku
            
            # Konwersja bajtów na liczbę całkowitą
            chunk_length = struct.unpack('>I', chunk_length_raw)[0]

            # Odczyt typu chunka (4 bajty)
            chunk_type = f.read(4).decode('ascii')

            # Odczyt danych chunka
            chunk_data = f.read(chunk_length)

            # Odczyt sumy kontrolnej CRC (4 bajty)
            crc = f.read(4)

            if chunk_type == 'IHDR':
                # Struktura IHDR
                width, height, bit_depth, color_type, compression_method, filter_method, interlace_method = struct.unpack('>IIBBBBB', chunk_data[0:13])
                
                # Mapowanie typu koloru w pliku PNG
                color_modes = {
                    0: "Greyscale",
                    2: "RGB",
                    3: "Palette index",
                    4: "Greyscale followed by Alpha",
                    6: "RGB followed by Alpha"
                }
                
                print(f"Atrybuty Obrazu (IHDR)")
                print(f"Rozdzielczość: {width} x {height} px")
                print(f"Głębia koloru: {bit_depth} bitów na kanał")
                print(f"Tryb koloru: {color_modes.get(color_type, 'Nieznany')}")
                if compression_method == 0:
                    print("Metoda kompresji: standard")
                else:
                    print('Nieznana metoda kompresji')
                if filter_method == 0:
                    print("Metoda filtracji: standard")
                else:
                    print('Nieznana metoda filtracji')
                if interlace_method == 0:
                    print("Interlace method: standard")
                else:
                    print('Nieznana metoda przeplotu')

            elif chunk_type == 'pHYs':
                # pHYs: Pixels per unit X(4), Pixels per unit Y(4), Unit specifier(1)
                ppux, ppuy, unit = struct.unpack('>IIB', chunk_data)
                if unit == 1:  # Unit 1 oznacza metry
                    dpi_x = round(ppux * 0.0254)
                    dpi_y = round(ppuy * 0.0254)
                    print(f"Częstotliwość próbkowania (pHYs): {ppux} px/m (~{dpi_x} DPI)")
                else:
                    print(f"Proporcje pikseli (pHYs): {ppux}:{ppuy}")

            elif chunk_type == 'gAMA':
                gamma = struct.unpack('>I', chunk_data)[0] / 100000.0
                print(f"Korekcja Gamma (gAMA): {gamma}")

            elif chunk_type == 'sRGB':
                rendering_intent = struct.unpack('B', chunk_data)[0]
                intents = ["Perceptual", "Relative Colorimetric", "Saturation", "Absolute Colorimetric"]
                print(f"Przestrzeń kolorów: sRGB (Intencja: {intents[rendering_intent]})")

            elif chunk_type == 'PLTE':
                num_colors = chunk_length // 3
                print(f"Paleta Kolorów (PLTE): {num_colors} kolorów")
                # Wypisanie max 3 kolorów (można zmienić limit)
                limit = 3
                for i in range(min(limit, num_colors)):
                    r, g, b = chunk_data[i*3:i*3+3]
                    print(f"  Kolor {i}: RGB({r}, {g}, {b})")

            elif chunk_type in ['tEXt', 'zTXt', 'iTXt']:
                print(f"--- Tekstowy chunk: {chunk_type} ---")

                if chunk_type == 'tEXt':
                    print("Znaleziono chunk tEXt")

                elif chunk_type == 'zTXt':
                    print("Znaleziono chunk zEXt")

                elif chunk_type == 'iTXt':
                    print("Znaleziono chunk iTXt")

            elif chunk_type == 'eXIf':
                print(f"Metadane EXIF (eXIf)")
                print(f"Znaleziono dane EXIF. Rozmiar bloku: {chunk_length} bajtów")
                
                parse_exif_full(chunk_data)

            elif chunk_type == 'IDAT':
                # Szczegóły dotyczące poszczególnych pikseli
                print(f"[IDAT] Segment danych obrazu. Długość: {chunk_length}")

            elif chunk_type == 'IEND':
                print(f"[IEND] Znacznik końca pliku.")
                curr = f.tell()
                f.seek(0, 2)
                end = f.tell()
                if end > curr:
                    print(f"Uwaga: Znaleziono {end - curr} bajtów za IEND!")
                break
            else:
                print(f"[INNY] Segment: {chunk_type} (Długość: {chunk_length})\n")

def read_value(exif_bytes, endian, typ, count, value):
    type_sizes = {
        1: 1,
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        7: 1
    }

    unit_size = type_sizes.get(typ, 1)
    size = unit_size * count

    if size <= 4:
        raw_inline = value.to_bytes(4, byteorder='little' if endian=='<' else 'big')[:size]

        if value + size <= len(exif_bytes):
            raw_offset = exif_bytes[value:value+size]
        else:
            raw_offset = raw_inline

        raw = raw_inline
    else:
        if value + size > len(exif_bytes):
            return "Offset poza zakresem"
        raw = exif_bytes[value:value+size]

    try:
        if typ == 2:  # ASCII
            return raw.decode('ascii', errors='ignore').strip('\x00')

        elif typ == 3:  # SHORT
            return struct.unpack(endian + 'H'*count, raw)

        elif typ == 4:  # LONG
            return struct.unpack(endian + 'I'*count, raw)

        elif typ == 5:  # RATIONAL
            vals = []
            for i in range(count):
                num, den = struct.unpack(endian + 'II', raw[i*8:(i+1)*8])
                vals.append(round(num/den, 4) if den != 0 else 0)
            return vals

        elif typ == 1:
            return list(raw)

        else:
            return raw

    except Exception as e:
        return f"Błąd: {e}"

def interpret_value(tag_name, value):
    if tag_name in VALUE_MAPS:
        mapping = VALUE_MAPS[tag_name]

        if isinstance(value, tuple):
            return [mapping.get(v, v) for v in value]
        else:
            return mapping.get(value, value)

    return value

def parse_ifd(exif_bytes, endian, offset, name="IFD"):
    print(f"\n--- {name} ---")

    num_entries = struct.unpack(endian + 'H', exif_bytes[offset:offset+2])[0]
    print(f"Liczba tagów: {num_entries}")

    pos = offset + 2
    tags = {}

    for i in range(num_entries):
        entry = exif_bytes[pos:pos+12]
        if len(entry) < 12:
            break

        tag, typ, count, value = struct.unpack(endian + 'HHII', entry)

        tags[tag] = value

        tag_name = EXIF_TAGS.get(tag, f"Unknown ({hex(tag)})")

        decoded_value = read_value(exif_bytes, endian, typ, count, value)
        decoded_value = interpret_value(tag_name, decoded_value)

        
        print(f"\nTag {i+1}")
        print(f"ID: {hex(tag)}")
        print(f"{tag_name}")
        print(f"Typ: {typ}")
        print(f"Liczba wartości: {count}")
        print(f"Wartość: {decoded_value}")
        print(f"RAW offset/value: {value}")

        pos += 12

    # offset do kolejnego IFD
    next_ifd_offset = struct.unpack(endian + 'I', exif_bytes[pos:pos+4])[0]

    return tags, next_ifd_offset

def parse_exif_full(exif_bytes):
    print("\n=== PEŁNA ANALIZA EXIF ===")

    # Endianness
    endian_flag = exif_bytes[:2]
    if endian_flag == b'II':
        endian = '<'
        print("Endianness: Little-endian")
    elif endian_flag == b'MM':
        endian = '>'
        print("Endianness: Big-endian")
    else:
        print("Nieznany format TIFF")
        return

    # Magic number
    magic = struct.unpack(endian + 'H', exif_bytes[2:4])[0]
    if magic != 42:
        print("Niepoprawny nagłówek TIFF")
        return

    # Offset IFD0
    offset_ifd0 = struct.unpack(endian + 'I', exif_bytes[4:8])[0]

    # === IFD0 ===
    tags_ifd0, next_ifd = parse_ifd(exif_bytes, endian, offset_ifd0, "IFD0")

    tags_exif = {}
    # === ExifIFD ===
    if 0x8769 in tags_ifd0:
        exif_offset = tags_ifd0[0x8769]
        print(f"\nZnaleziono ExifIFD pod offsetem: {exif_offset}")
        parse_ifd(exif_bytes, endian, exif_offset, "ExifIFD")

    # === GPSIFD ===
    if 0x8825 in tags_ifd0:
        gps_offset = tags_ifd0[0x8825]
        print(f"\nZnaleziono GPSIFD pod offsetem: {gps_offset}")
        parse_ifd(exif_bytes, endian, gps_offset, "GPSIFD")

    # === InteropIFD ===
    if 0xA005 in tags_exif:
        interop_offset = tags_exif[0xA005]
        print(f"\nZnaleziono InteropIFD pod offsetem: {interop_offset}")
        parse_ifd(exif_bytes, endian, interop_offset, "InteropIFD")

def anonymize_png(input_path, output_path):
    # Lista chunków krytycznych
    REQUIRED_CHUNKS = {b'IHDR', b'PLTE', b'IDAT', b'IEND'}
    
    try:
        with open(input_path, 'rb') as f_in, open(output_path, 'wb') as f_out:
            
            # Kopiowanie sygnatury PNG (8 bajtów)
            signature = f_in.read(8)
            if signature != b'\x89PNG\r\n\x1a\n':
                print("Błąd: To nie jest poprawny plik PNG!")
                return
            f_out.write(signature)

            # Licznik usuniętych bajtów do podsumowania
            bytes_removed = 0
            
            while True:
                # Odczyt długości (4 bajty)
                length_raw = f_in.read(4)
                if not length_raw:
                    break
                
                # Odczyt typu (4 bajty)
                chunk_type = f_in.read(4)
                chunk_length = struct.unpack('>I', length_raw)[0]
                
                # Odczyt danych i sumy kontrolnej CRC
                chunk_data = f_in.read(chunk_length)
                chunk_crc = f_in.read(4)

                # Decyzja o zapisie
                if chunk_type in REQUIRED_CHUNKS:
                    f_out.write(length_raw)
                    f_out.write(chunk_type)
                    f_out.write(chunk_data)
                    f_out.write(chunk_crc)
                else:
                    # Sumowanie usuniętych danych (długość + typ + dane + CRC)
                    bytes_removed += (4 + 4 + chunk_length + 4)
                    print(f"Usunięto chunk: {chunk_type.decode('ascii', errors='ignore')}")

                if chunk_type == b'IEND':
                    break

            print(f"\nOczyszczony plik zapisany jako: {output_path}")
            print(f"Usunięto łącznie {bytes_removed} bajtów zbędnych metadanych.")

    except FileNotFoundError:
        print(f"Błąd: Nie odnaleziono pliku '{input_path}'.")
    except Exception as e:
        print(f"Wystąpił błąd: {e}")

#analyze_png_attributes('path.png')
#fourier_transform('path.png')
#fourier_transform_rgb('path.png')
#convert_jpg_to_png_with_exif("path_input.jpg", "path_output.png")
#append_secret_data('path.png', 'Text to append after IEND')
#anonymize_png('path_input.png', 'path_output.png')
