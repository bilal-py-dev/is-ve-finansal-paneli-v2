import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from google import genai
import database

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_KULLANICI = os.getenv("ADMIN_KULLANICI", "admin")
ADMIN_SIFRE = os.getenv("ADMIN_SIFRE", "123456")

app = FastAPI(title="İş ve Finansal Yönetim Paneli")
database.tablolari_olustur()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def giris_kontrol(request: Request):
    return request.cookies.get("oturum_yetkisi") == "aktif_yonetici"

def sayfa_verisi_hazirla(request: Request, ai_analiz: str = None, sorulan_soru: str = ""):
    musteriler, finanslar = database.verileri_getir()
    ozet = database.finansal_ozet_getir()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "musteriler": musteriler,
            "finanslar": finanslar,
            "toplam_gelir": ozet["toplam_gelir"],
            "toplam_gider": ozet["toplam_gider"],
            "net_bakiye": ozet["net_kar"],
            "bekleyen_alacak": ozet["bekleyen_alacak"],
            "aktif_proje": ozet["aktif_proje_sayisi"],
            "tamamlanan_proje": ozet["tamamlanan_proje_sayisi"],
            "ai_analiz": ai_analiz,
            "sorulan_soru": sorulan_soru,
        }
    )

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
    return sayfa_verisi_hazirla(request)

@app.get("/excel-rapor")
async def excel_rapor_indir(request: Request):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    csv_icerik = database.csv_rapor_olustur()
    return Response(
        content=csv_icerik,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=is_ve_finansal_rapor.csv"}
    )

@app.post("/ai-analiz", response_class=HTMLResponse)
async def yapay_zeka_analiz(request: Request, ozel_soru: str = Form("")):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)

    if not GEMINI_API_KEY:
        return sayfa_verisi_hazirla(request, ai_analiz="⚠️ .env dosyasında GEMINI_API_KEY tanımlı değil! Lütfen API anahtarını ekle.")

    veri_ozeti = database.ai_icin_ozet_metni()
    if ozel_soru.strip():
        prompt = (
            f"Sen profesyonel bir işletme ve finans danışmanısın. Kullanıcının şu sorusuna aşağıdaki gerçek verilere dayanarak "
            f"kısa, net ve uygulanabilir Türkçe yanıt ver:\n\nSORU: {ozel_soru.strip()}\n\nVERİLER:\n{veri_ozeti}"
        )
    else:
        prompt = (
            f"Sen profesyonel bir finans ve iş geliştirme danışmanısın. Aşağıdaki freelancer/ajans verilerini inceleyip "
            f"en fazla 4 maddelik kısa, net ve eyleme dönük Türkçe analiz ve tavsiye ver:\n\n{veri_ozeti}"
        )
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        try:
            res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
        except Exception:
            res = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
        analiz = res.text
    except Exception as e:
        analiz = f"❌ AI Bağlantı Hatası: {str(e)}"

    return sayfa_verisi_hazirla(request, ai_analiz=analiz, sorulan_soru=ozel_soru.strip())

@app.post("/musteri-ekle")
async def yeni_musteri(
    request: Request,
    ad_soyad: str = Form(...),
    proje_adi: str = Form(...),
    ucret: float = Form(...),
    durum: str = Form(...),
    teslim_tarihi: str = Form("")
):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    database.musteri_ekle(ad_soyad, proje_adi, ucret, durum, teslim_tarihi)
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

@app.get("/teklif/{musteri_id}", response_class=HTMLResponse)
async def teklif_belgesi(request: Request, musteri_id: int):
    if not giris_kontrol(request):
        return RedirectResponse(url="/login", status_code=303)
    musteri = database.tek_musteri_getir(musteri_id)
    if not musteri:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="teklif.html", context={"m": musteri})
