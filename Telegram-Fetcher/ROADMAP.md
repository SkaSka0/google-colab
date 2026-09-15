# 🗺️ Roadmap — Telegram Fetcher

Dokumen ini berisi rencana perbaikan dan pengembangan untuk proyek **Telegram Fetcher**, diurutkan dari yang paling urgent (blocker) hingga peningkatan jangka panjang.

Status: `Draft` — silakan diskusikan/update lewat Issue atau PR.

> **Scope platform**: proyek ini didesain khusus untuk berjalan di **Google Colab** dan tidak ditargetkan untuk portable ke platform lain (VPS, server umum, dsb). Keputusan ini disengaja agar development lebih fokus dan sederhana. Karena itu, dependensi ke Colab (`google.colab.drive`, `google.colab.userdata`, IPython magic di `main.py`, dll) **bukan** sesuatu yang perlu dihindari atau diabstraksi — justru dianggap sebagai bagian normal dari arsitektur.

---

## Fase 0 — Critical Blocker

> Bot saat ini **tidak bisa berjalan sama sekali**. Fase ini harus selesai lebih dulu sebelum fase lain dikerjakan.

- [x] **Fix import `colab-fetcher` → `colab_fetcher`**
  - Lokasi: `colab_fetcher/__main__.py`
  - Masalah: `colab-fetcher` (dengan tanda hubung) bukan identifier Python yang valid, menyebabkan `SyntaxError` saat module di-load.
  - Baris terkait:
    ```python
    from colab-fetcher import CONFIG_PATH
    from colab-fetcher import load_credentials
    from colab-fetcher.utils.client import app
    from colab-fetcher.utils.logging import logger
    ```

- [x] **Fix `NameError`/logic error di `queue_command`**
  - Lokasi: `colab_fetcher/__main__.py`
  - Masalah: variabel `filename` dipakai (`smart_truncate_filename(filename)`) sebelum pernah didefinisikan jika `active_downloads` kosong, dan dipanggil di luar loop `download_queue._queue` sehingga daftar file di `/queue` menampilkan nama yang sama (stale) untuk semua item.

---

## Fase 1 — Bug Fix Fungsional

> Bot sudah bisa jalan, tapi ada behavior yang salah atau tidak sesuai ekspektasi.

- [ ] State `"queued"` langsung di-clear di blok `finally` pada `handle_file_upload`, sehingga tracking state user tidak pernah benar-benar tersimpan.
- [ ] `is_allowed_file()` selalu mengembalikan `True` — validasi tipe file jadi dead code, padahal ada pesan error `invalid_type` yang seharusnya dipakai. Perlu diputuskan: implementasi validasi sungguhan (pakai dict `EXTENSIONS` yang sudah ada) atau hapus fiturnya.
- [ ] `get_file_extension()` tidak menangani `message.animation` (GIF), padahal handler filter menerimanya (`filters.animation`) — hasil ekstensi jatuh ke default `.bin`.
- [ ] Inkonsistensi default `download_path`: `main.py` set default `/content/media_toolkit/downloads`, sementara `get_output_directory()` di `__main__.py` default ke `/content/downloads`.
- [ ] Potensi race condition di `batch_tasks` / `batch_buffer` saat `send_batch_message` sedang melakukan cleanup (`pop`) bersamaan dengan file baru masuk — sebaiknya dilindungi lock seperti `state_lock`.
- [ ] Review alur exception `asyncio.CancelledError` di `download_with_progress` — ada risiko `file_path` diakses dalam kondisi yang belum tentu valid.

---

## Fase 2 — Reliability & Data Integrity

> Fokus pada ketahanan bot saat dipakai dalam jangka panjang / beban lebih berat.

- [ ] `user_state.json` di-overwrite penuh tiap kali tanpa atomic write (write-to-temp-then-rename) — berisiko corrupt jika proses mati di tengah jalan.
- [ ] Hindari akses langsung ke atribut privat `download_queue._queue`; gunakan struktur data terpisah sebagai "source of truth" untuk keperluan display/listing.
- [ ] Tidak ada pengecekan ukuran file / sisa disk space sebelum download dimulai — pesan error `file_too_large` sudah didefinisikan tapi tidak pernah dipanggil.
- [ ] Tidak ada retry logic otomatis untuk `network_error` — saat ini user harus re-upload manual.
- [ ] Banyak titik `except: pass` yang menelan semua exception tanpa logging — menyulitkan debugging masalah lain yang ter-mask.

---

## Fase 3 — Refactor Struktural

> Merapikan arsitektur kode setelah fungsionalitas stabil.

- [ ] Pecah `colab_fetcher/__main__.py` (500+ baris) menjadi modul-modul terpisah, contoh struktur:
  ```
  colab_fetcher/
  ├── handlers/
  │   ├── commands.py      # /start, /help, /tgupload, /queue, /cancelall
  │   └── upload.py        # handle_file_upload, callback cancel
  ├── core/
  │   ├── queue_worker.py  # queue_worker, download_with_progress
  │   ├── batching.py      # send_batch_message + buffer state
  │   └── state.py         # user state management
  └── utils/
      ├── filename.py      # sanitize, truncate, get_unique_filename, get_extension
      └── messages.py      # semua template teks (get_start_message, get_progress_text, dll)
  ```
- [ ] Enkapsulasi global dict (`active_downloads`, `completed_downloads`, `batch_buffer`, `batch_tasks`) ke dalam class/state manager, alih-alih shared mutable state yang tersebar di banyak fungsi.
- [ ] `CONFIG_PATH` saat ini hardcoded absolute path (`/content/...`) sehingga tidak portable di luar Colab — pertimbangkan env var atau path relatif terhadap package.
- [ ] Migrasi user-facing string (pesan bot, error messages, progress text, dll di `colab_fetcher/__main__.py`) dari Bahasa Indonesia ke Bahasa Inggris. Dikerjakan sebagai item terpisah dari migrasi kode internal (nama fungsi/variabel/komentar), agar perubahan wording bisa direview sendiri. Daftar fungsi yang perlu disentuh: `get_start_message`, `get_tgupload_message`, help text di `help_handler`, `get_progress_text`, `download_summary_message`, `queue_command` text, `cancel_all_command` text, dan semua entri di `send_error`'s `error_messages` dict.
- [ ] Terapkan prinsip satu tanggung jawab per fungsi (Single Responsibility). Beberapa fungsi seperti `handle_file_upload` dan `download_with_progress` saat ini melakukan banyak hal sekaligus (queue management, state tracking, batching, progress reporting, error handling) — pecah menjadi fungsi-fungsi yang lebih kecil dan fokus saat refactor modul terkait.

---

## Fase 4 — Testing

> Saat ini belum ada test sama sekali di repo.

- [ ] Unit test untuk fungsi pure (tidak butuh Telegram API): `sanitize_filename`, `smart_truncate_filename`, `get_file_extension`, `ext_from_mime`, `format_duration`, `get_unique_filename`.
- [ ] Test untuk state management (`load_user_state`, `save_user_state`, `set_user_state`, `get_user_state`, `clear_user_state`) menggunakan temp file.
- [ ] Integration test dasar untuk queue worker logic dengan mock Pyrogram `Client` / `Message`.
- [ ] Setup CI (GitHub Actions) minimal untuk menjalankan lint + test pada setiap push/PR.

---

## Fase 5 — Dokumentasi

> Bisa dikerjakan paralel dengan Fase 3 dan 4.

- [ ] **README.md** komprehensif: deskripsi proyek, cara pakai di Google Colab (step by step), daftar command, struktur folder.
- [ ] **CONTRIBUTING.md**: konvensi kode, cara setup dev environment, cara submit PR.
- [ ] Docstring untuk semua fungsi publik (saat ini `__main__.py` belum punya docstring sama sekali).
- [ ] Dokumentasi format `credentials.json` dan `user_state.json`, termasuk contoh isi serta field wajib/opsional.
- [ ] **CHANGELOG.md**, mulai dicatat dari sekarang termasuk bug fix di roadmap ini.
- [ ] (Opsional) Diagram alur: upload → queue → download → notifikasi, untuk memudahkan kontributor baru memahami logic batching + queue + progress.

---

## Fase 6 — Peningkatan Fitur (Nice-to-have)

> Di luar scope "fix & clean", untuk didiskusikan sebagai arah pengembangan proyek ke depan.

- [ ] Fitur cancel per-file langsung dari `/queue` (saat ini cancel button hanya ada di progress message yang sedang aktif).
- [ ] Rate limiting per user untuk mencegah spam upload.
- [ ] Dukungan resume download setelah gagal.
- [ ] Opsi kompresi/convert otomatis (misal video ke format tertentu) — jika sesuai visi proyek.
- [ ] Eksplorasi multi-worker (concurrent download) sebagai alternatif `queue_worker()` tunggal — perlu pertimbangan trade-off dengan keterbatasan resource Colab.

---

## Urutan Eksekusi yang Direkomendasikan

```
Fase 0 (blocker)      →  bot bisa jalan
Fase 1 (bug fix)      →  bot berperilaku benar
Fase 2 (reliability)  →  bot stabil dipakai
Fase 3 (refactor)     →  kode mudah dikembangkan
Fase 4 (testing)      →  perubahan ke depan aman, tidak regresi
Fase 5 (dokumentasi)  →  paralel dengan Fase 3 & 4
Fase 6 (fitur baru)   →  setelah fondasi solid
```
