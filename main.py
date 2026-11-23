import os
import io
import csv
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from google import genai
import database

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_KULLANICI = os.getenv("ADMIN_KULLANICI", "admin")
ADMIN_SIFRE = os.getenv("ADMIN_SIFRE", "123456")

app = FastAPI()
database.tablolari_olustur()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def giris_kontrol(request: Request):
    return request.cookies.get("oturum_yetkisi") == "aktif_yonetici"

@app.get("/login", response_class=HTMLResponse)
async def login_sayfasi(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"hata": None})

@app.post("/login")
async def login_islem(request: Request, kullanici_adi: str = Form(...), sifre: str = Form(...)):
    if kullanici_adi == ADMIN_KULLANICI and sifre == ADMIN_SIFRE:
        cevap = RedirectResponse(url="/", status_code=303)
        cevap.set_cookie(key="oturum_yetkisi", value="aktif_yonetici", httponly=True)
        return cevap
    return templates.TemplateResponse(request=request, name="login.html", context={"hata": "Kullanıcı adı veya şifre hatalı!"})

@app.get("/logout")
async def cikis_yap():
    cevap = RedirectResponse(url="/login", status_code=303)
    cevap.delete_cookie("oturum_yetkisi")
    return cevap

@app.get("/", response_class=HTMLResponse)
async def ana_sayfa(request: Request):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    musteriler, finanslar = database.verileri_getir()
    gelir = sum(f["tutar"] for f in finanslar if f["tur"] == "Gelir")
    gider = sum(f["tutar"] for f in finanslar if f["tur"] == "Gider")
    return templates.TemplateResponse(request=request, name="index.html", context={
        "musteriler": musteriler, "finanslar": finanslar,
        "toplam_gelir": gelir, "toplam_gider": gider,
        "net_bakiye": gelir - gider, "ai_analiz": None
    })

@app.get("/excel-rapor")
async def excel_rapor_indir(request: Request):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    musteriler, finanslar = database.verileri_getir()
    
    cikti = io.StringIO()
    cikti.write("\ufeff")
    yazici = csv.writer(cikti, delimiter=";")
    
    yazici.writerow(["--- MÜŞTERİ VE PROJE LİSTESİ ---"])
    yazici.writerow(["ID", "Müşteri Adı", "Proje Adı", "Ücret (TL)", "Durum"])
    for m in musteriler:
        yazici.writerow([m["id"], m["ad_soyad"], m["proje_adi"], m["ucret"], m["durum"]])
        
    yazici.writerow([])
    yazici.writerow(["--- FİNANSAL KASA HAREKETLERİ ---"])
    yazici.writerow(["ID", "Tür", "Açıklama", "Tutar (TL)"])
    for f in finanslar:
        yazici.writerow([f["id"], f["tur"], f["aciklama"], f["tutar"]])

    cikti.seek(0)
    return StreamingResponse(
        iter([cikti.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=is_ve_finansal_rapor.csv"}
    )

@app.post("/ai-analiz", response_class=HTMLResponse)
async def yapay_zeka_analiz(request: Request):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    musteriler, finanslar = database.verileri_getir()
    gelir = sum(f["tutar"] for f in finanslar if f["tur"] == "Gelir")
    gider = sum(f["tutar"] for f in finanslar if f["tur"] == "Gider")
    net = gelir - gider
    isler = "\n".join([f"- {m['ad_soyad']}: {m['proje_adi']} ({m['ucret']} TL) - {m['durum']}" for m in musteriler])
    hareketler = "\n".join([f"- {f['tur']}: {f['aciklama']} ({f['tutar']} TL)" for f in finanslar])
    prompt = f"Profesyonel finans danışmanı olarak en fazla 4 maddelik kısa Türkçe özet ve tavsiye ver:\nGelir: {gelir} TL, Gider: {gider} TL, Net: {net} TL\nİşler:\n{isler}\nHareketler:\n{hareketler}"
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        res = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
        analiz = res.text
    except Exception as e:
        analiz = f"API Hatası (API anahtarını kontrol et): {str(e)}"
    return templates.TemplateResponse(request=request, name="index.html", context={
        "musteriler": musteriler, "finanslar": finanslar,
        "toplam_gelir": gelir, "toplam_gider": gider,
        "net_bakiye": net, "ai_analiz": analiz
    })

@app.post("/musteri-ekle")
async def yeni_musteri(request: Request, ad_soyad: str = Form(...), proje_adi: str = Form(...), ucret: float = Form(...), durum: str = Form(...)):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.musteri_ekle(ad_soyad, proje_adi, ucret, durum)
    return RedirectResponse(url="/", status_code=303)

@app.post("/musteri-durum/{musteri_id}")
async def guncelle_musteri(request: Request, musteri_id: int, durum: str = Form(...)):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.musteri_durum_guncelle(musteri_id, durum)
    return RedirectResponse(url="/", status_code=303)

@app.post("/musteri-sil/{musteri_id}")
async def sil_musteri(request: Request, musteri_id: int):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.musteri_sil(musteri_id)
    return RedirectResponse(url="/", status_code=303)

@app.post("/finans-ekle")
async def yeni_finans(request: Request, tur: str = Form(...), aciklama: str = Form(...), tutar: float = Form(...)):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.finans_ekle(tur, aciklama, tutar)
    return RedirectResponse(url="/", status_code=303)

@app.post("/finans-sil/{finans_id}")
async def sil_finans(request: Request, finans_id: int):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.finans_sil(finans_id)
    return RedirectResponse(url="/", status_code=303)
