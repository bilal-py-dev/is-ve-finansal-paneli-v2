import sqlite3
import csv
import io
from datetime import datetime

DB_DOSYASI = "is_finans.db"

def baglanti_kur():
    conn = sqlite3.connect(DB_DOSYASI)
    conn.row_factory = sqlite3.Row
    return conn

def tablolari_olustur():
    conn = baglanti_kur()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS musteriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            proje_adi TEXT NOT NULL,
            ucret REAL NOT NULL,
            durum TEXT DEFAULT 'Devam Ediyor',
            teslim_tarihi TEXT DEFAULT '',
            olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tur TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            tutar REAL NOT NULL,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Eski veritabanı varsa eksik sütunları veri kaybı olmadan ekle
    musteri_sutunlar = [row["name"] for row in cursor.execute("PRAGMA table_info(musteriler)").fetchall()]
    if "teslim_tarihi" not in musteri_sutunlar:
        cursor.execute("ALTER TABLE musteriler ADD COLUMN teslim_tarihi TEXT DEFAULT ''")
    if "olusturma_tarihi" not in musteri_sutunlar:
        cursor.execute("ALTER TABLE musteriler ADD COLUMN olusturma_tarihi TEXT DEFAULT ''")

    finans_sutunlar = [row["name"] for row in cursor.execute("PRAGMA table_info(finans)").fetchall()]
    if "tarih" not in finans_sutunlar:
        cursor.execute("ALTER TABLE finans ADD COLUMN tarih TEXT DEFAULT ''")

    conn.commit()
    conn.close()

def musteri_ekle(ad_soyad, proje_adi, ucret, durum="Devam Ediyor", teslim_tarihi=""):
    conn = baglanti_kur()
    cursor = conn.cursor()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        "INSERT INTO musteriler (ad_soyad, proje_adi, ucret, durum, teslim_tarihi, olusturma_tarihi) VALUES (?, ?, ?, ?, ?, ?)",
        (ad_soyad.strip(), proje_adi.strip(), float(ucret), durum, teslim_tarihi.strip(), simdi)
    )
    if durum == "Tamamlandı":
        cursor.execute(
            "INSERT INTO finans (tur, aciklama, tutar, tarih) VALUES (?, ?, ?, ?)",
            ("Gelir", f"Proje Geliri: {ad_soyad.strip()} - {proje_adi.strip()}", float(ucret), simdi)
        )
    conn.commit()
    conn.close()

def musteri_durum_guncelle(musteri_id, yeni_durum):
    conn = baglanti_kur()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM musteriler WHERE id = ?", (musteri_id,))
    m = cursor.fetchone()
    if m:
        cursor.execute("UPDATE musteriler SET durum = ? WHERE id = ?", (yeni_durum, musteri_id))
        if m["durum"] != "Tamamlandı" and yeni_durum == "Tamamlandı":
            simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor.execute(
                "INSERT INTO finans (tur, aciklama, tutar, tarih) VALUES (?, ?, ?, ?)",
                ("Gelir", f"Proje Geliri: {m['ad_soyad']} - {m['proje_adi']}", m["ucret"], simdi)
            )
    conn.commit()
    conn.close()

def musteri_sil(musteri_id):
    conn = baglanti_kur()
    conn.execute("DELETE FROM musteriler WHERE id = ?", (musteri_id,))
    conn.commit()
    conn.close()

def finans_ekle(tur, aciklama, tutar):
    conn = baglanti_kur()
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "INSERT INTO finans (tur, aciklama, tutar, tarih) VALUES (?, ?, ?, ?)",
        (tur, aciklama.strip(), float(tutar), simdi)
    )
    conn.commit()
    conn.close()

def finans_sil(finans_id):
    conn = baglanti_kur()
    conn.execute("DELETE FROM finans WHERE id = ?", (finans_id,))
    conn.commit()
    conn.close()

def verileri_getir():
    conn = baglanti_kur()
    musteriler = conn.execute("SELECT * FROM musteriler ORDER BY id DESC").fetchall()
    finanslar = conn.execute("SELECT * FROM finans ORDER BY id DESC").fetchall()
    conn.close()
    return musteriler, finanslar

def finansal_ozet_getir():
    musteriler, finanslar = verileri_getir()
    toplam_gelir = sum(f["tutar"] for f in finanslar if f["tur"] == "Gelir")
    toplam_gider = sum(f["tutar"] for f in finanslar if f["tur"] == "Gider")
    net_kar = toplam_gelir - toplam_gider
    bekleyen_alacak = sum(m["ucret"] for m in musteriler if m["durum"] != "Tamamlandı")
    aktif_proje_sayisi = sum(1 for m in musteriler if m["durum"] != "Tamamlandı")
    tamamlanan_proje_sayisi = sum(1 for m in musteriler if m["durum"] == "Tamamlandı")

    return {
        "toplam_gelir": round(toplam_gelir, 2),
        "toplam_gider": round(toplam_gider, 2),
        "net_kar": round(net_kar, 2),
        "bekleyen_alacak": round(bekleyen_alacak, 2),
        "aktif_proje_sayisi": aktif_proje_sayisi,
        "tamamlanan_proje_sayisi": tamamlanan_proje_sayisi,
    }

def csv_rapor_olustur():
    musteriler, finanslar = verileri_getir()
    ozet = finansal_ozet_getir()
    cikti = io.StringIO()
    yazici = csv.writer(cikti, delimiter=";")

    yazici.writerow(["=== GENEL FINANSAL OZET ==="])
    yazici.writerow(["Toplam Gelir (TL)", "Toplam Gider (TL)", "Net Kar (TL)", "Bekleyen Alacak (TL)"])
    yazici.writerow([ozet["toplam_gelir"], ozet["toplam_gider"], ozet["net_kar"], ozet["bekleyen_alacak"]])
    yazici.writerow([])

    yazici.writerow(["=== MUSTERI VE PROJE LISTESI ==="])
    yazici.writerow(["ID", "Musteri Adi", "Proje Adi", "Ucret (TL)", "Durum", "Teslim Tarihi", "Kayit Tarihi"])
    for m in musteriler:
        yazici.writerow([m["id"], m["ad_soyad"], m["proje_adi"], m["ucret"], m["durum"], m["teslim_tarihi"] or "-", m["olusturma_tarihi"] or "-"])
    yazici.writerow([])

    yazici.writerow(["=== GELIR VE GIDER HAREKETLERI ==="])
    yazici.writerow(["ID", "Tur", "Aciklama", "Tutar (TL)", "Tarih"])
    for f in finanslar:
        yazici.writerow([f["id"], f["tur"], f["aciklama"], f["tutar"], f["tarih"] or "-"])

    return cikti.getvalue().encode("utf-8-sig")

def ai_icin_ozet_metni():
    musteriler, finanslar = verileri_getir()
    ozet = finansal_ozet_getir()
    satirlar = [
        f"Toplam Gelir: {ozet['toplam_gelir']} TL",
        f"Toplam Gider: {ozet['toplam_gider']} TL",
        f"Net Kar: {ozet['net_kar']} TL",
        f"Bekleyen Proje Alacagi: {ozet['bekleyen_alacak']} TL",
        f"Aktif Proje Sayisi: {ozet['aktif_proje_sayisi']} | Tamamlanan: {ozet['tamamlanan_proje_sayisi']}",
        "\nSon Projeler:"
    ]
    for m in musteriler[:10]:
        satirlar.append(f"- {m['ad_soyad']} | {m['proje_adi']} | {m['ucret']} TL | {m['durum']} | Teslim: {m['teslim_tarihi'] or 'Belirtilmedi'}")
    satirlar.append("\nSon Finans Hareketleri:")
    for f in finanslar[:15]:
        satirlar.append(f"- [{f['tur']}] {f['aciklama']}: {f['tutar']} TL ({f['tarih'] or '-'})")
    return "\n".join(satirlar)

def tek_musteri_getir(musteri_id):
    conn = baglanti_kur()
    m = conn.execute("SELECT * FROM musteriler WHERE id = ?", (musteri_id,)).fetchone()
    conn.close()
    return m
