# ORC-WIN

Aplikasi desktop ringan untuk Windows 10/11 (64-bit) yang menyediakan fitur _selection-based OCR_. Pengguna dapat memilih area tertentu pada layar dan aplikasi akan langsung mengenali teks di area tersebut menggunakan mesin Tesseract (dukungan bahasa Indonesia dan Inggris). Rilis ini memanfaatkan PySide6 terbaru serta optimasi pipeline OCR untuk memastikan kinerja mulus di Python 3.13.

## Fitur Utama

- **Pemilihan area layar cepat** dengan tampilan overlay gelap seperti Snipping Tool.
- **Pintasan keyboard** `Ctrl + Shift + O` untuk langsung masuk ke mode seleksi.
- **Hotkey global bawaan** untuk `Ctrl + Shift + O` sehingga pintasan bekerja walau jendela aplikasi tidak fokus.
- **Mesin OCR Tesseract** dengan dukungan bahasa Indonesia (`ind`) dan Inggris (`eng`).
- **Antarmuka sederhana**: tombol "Select Area", tombol "Copy to Clipboard", dan kotak teks hasil.
- **Proses berjalan di latar** sehingga UI tetap responsif.
- **Hasil OCR siap salin** hanya dengan satu klik.

## Persyaratan Sistem

- Windows 10 atau Windows 11 (64-bit)
- Python 3.11 – 3.13 (disarankan menggunakan Python 3.13 untuk performa terbaik)
- Tesseract OCR 5.x (dengan bahasa `ind` dan `eng` terpasang)
- GPU tidak diperlukan; CPU dual-core modern sudah mencukupi

## Instalasi Tesseract

1. Unduh _installer_ Tesseract resmi dari proyek [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
2. Saat instalasi, pastikan opsi bahasa **English** dan **Indonesian** dicentang.
3. Catat lokasi pemasangan, contoh: `C:\Program Files\Tesseract-OCR\tesseract.exe`.
4. (Opsional) Tambahkan lokasi tersebut ke variabel lingkungan `PATH` atau set variabel `TESSERACT_CMD` saat menjalankan aplikasi:
   ```powershell
   setx TESSERACT_CMD "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
   ```

## Menjalankan Aplikasi Secara Langsung

1. Siapkan lingkungan Python (contoh menggunakan PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

2. Jalankan aplikasi:
   ```powershell
   python src\main.py
   ```

## Cara Pakai

1. Jalankan aplikasi, antarmuka utama akan menampilkan dua tombol dan kotak teks kosong.
2. Klik tombol **Select Area** atau tekan pintasan `Ctrl + Shift + O` (pintasan ini bersifat global di Windows 10/11).
3. Layar akan meredup. Seret kursor untuk memilih area yang ingin dikenali.
4. Lepaskan klik. Aplikasi otomatis menangkap area tersebut dan menjalankan OCR.
5. Hasil teks muncul di kotak teks. Klik **Copy to Clipboard** untuk menyalin ke clipboard Windows.
6. Ulangi proses kapan pun dibutuhkan tanpa harus menutup aplikasi.

## Membuat Versi Portable (.exe)

Gunakan PyInstaller untuk membuat paket mandiri:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --name ORC-WIN src\main.py
```

Berkas `.exe` akan tersedia di folder `dist`. Pastikan `tesseract.exe` dapat ditemukan melalui `PATH` atau bundelkan bersama file `tessdata` jika membuat distribusi khusus. Sertakan `vcruntime140.dll` (biasanya sudah ada di Windows 10) bila menggunakan PyInstaller satu berkas.

## Kustomisasi

- Ubah bahasa OCR dengan mengedit `src/ocr.py` atau menggunakan variabel lingkungan `OCR_LANGUAGES` (tambahkan sendiri sebelum membuat `OcrConfig`).
- Jika ingin mengganti pintasan, ubah baris `QKeySequence("Ctrl+Shift+O")` di `src/main.py`.
- Untuk mengatur path Tesseract secara manual, gunakan variabel lingkungan `TESSERACT_CMD` atau edit properti `tesseract_cmd` pada `OcrConfig`.

## Pemecahan Masalah

- **Tesseract tidak ditemukan** – pastikan `tesseract.exe` bisa diakses melalui `PATH` atau set variabel `TESSERACT_CMD`. Aplikasi akan menampilkan pesan kesalahan yang jelas bila executable tidak ditemukan. Versi terbaru juga mencoba mendeteksi Tesseract otomatis di `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- **Hotkey global tidak aktif** – pastikan tidak ada aplikasi lain yang menggunakan kombinasi `Ctrl + Shift + O`. Jika konflik terjadi, ganti kombinasi di `src/main.py` atau jalankan aplikasi dengan hak akses administrator.
- **Akurasi kurang baik** – perbaiki pencahayaan pada area tangkapan, atau tambahkan argumen ekstra pada `OcrConfig.extra_flags` (misal `--dpi 200`).

## Changelog Singkat

- Migrasi dari PyQt5 ke PySide6 untuk dukungan jangka panjang dan performa yang lebih baik di Windows 10.
- Penambahan hotkey global bawaan berbasis Win32 `RegisterHotKey` dengan pelepasan otomatis saat aplikasi ditutup sehingga tetap kompatibel dengan Python 3.13.
- Pipeline OCR diperbarui dengan praproses citra ringan dan penanganan kesalahan yang lebih informatif.
- Overlay seleksi kini mendukung multi-monitor dan pembatalan cepat dengan tombol `Esc`/`Q`.
- Optimalisasi tambahan untuk Python 3.13, termasuk dukungan DPI tinggi yang lebih akurat serta deteksi otomatis lokasi `tesseract.exe` di Windows 10/11.

## Lisensi

Proyek ini dirilis dengan lisensi MIT. Lihat berkas [LICENSE](LICENSE).
