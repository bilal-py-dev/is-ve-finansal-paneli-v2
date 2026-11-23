import sqlite3

def baglanti_kur():
    conn = sqlite3.connect("is_finans.db")
    conn.row_factory = sqlite3.Row
    return conn

def tablolari_olustur():
    conn = baglanti_kur()
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS musteriler (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ad_soyad TEXT NOT NULL,
        proje_adi TEXT NOT NULL, ucret REAL NOT NULL, durum TEXT DEFAULT 'Devam Ediyor')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS finans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tur TEXT NOT NULL,
        aciklama TEXT NOT NULL, tutar REAL NOT NULL)""")
    conn.commit()
    conn.close()

def musteri_ekle(ad_soyad, proje_adi, ucret, durum="Devam Ediyor"):
    conn = baglanti_kur()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO musteriler (ad_soyad, proje_adi, ucret, durum) VALUES (?, ?, ?, ?)", (ad_soyad, proje_adi, ucret, durum))
    if durum == "Tamamlandı":
        cursor.execute("INSERT INTO finans (tur, aciklama, tutar) VALUES (?, ?, ?)", ("Gelir", f"Proje Geliri: {ad_soyad} - {proje_adi}", ucret))
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
            cursor.execute("INSERT INTO finans (tur, aciklama, tutar) VALUES (?, ?, ?)", ("Gelir", f"Proje Geliri: {m['ad_soyad']} - {m['proje_adi']}", m["ucret"]))
    conn.commit()
    conn.close()

def musteri_sil(musteri_id):
    conn = baglanti_kur()
    conn.execute("DELETE FROM musteriler WHERE id = ?", (musteri_id,))
    conn.commit()
    conn.close()

def finans_ekle(tur, aciklama, tutar):
    conn = baglanti_kur()
    conn.execute("INSERT INTO finans (tur, aciklama, tutar) VALUES (?, ?, ?)", (tur, aciklama, tutar))
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
