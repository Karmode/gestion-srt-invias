from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Configuracion:
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "gestion_srt")
    secret_key: str = os.getenv("SECRET_KEY", "cambia_esta_clave_por_una_muy_larga_y_segura")
    admin_inicial_password: str | None = os.getenv("ADMIN_INICIAL_PASSWORD")
    instructivo_pdf_url: str = os.getenv("INSTRUCTIVO_PDF_URL", "")
    instructivo_video_url: str = os.getenv("INSTRUCTIVO_VIDEO_URL", "")
    # Herramientas externas — Sección 7
    az_digital_url: str = os.getenv("AZ_DIGITAL", "")
    klic_2_url: str = os.getenv("KLIC_2", "")
    adres_url: str = os.getenv("ADRES", "")
    secop_url: str = os.getenv("SECOP", "")
    pdf_h_url: str = os.getenv("PDF_H", "")
    
    # Nuevas variables de antecedentes/control
    url_procuraduria: str = os.getenv("URL_PROCURADURIA", "")
    url_contraloria: str = os.getenv("URL_CONTRALORIA", "")
    url_pol_antecedentes: str = os.getenv("URL_POL_ANTECEDENTES", "")
    url_pol_rcmc: str = os.getenv("URL_POL_RCMC", "")
    url_rut: str = os.getenv("URL_RUT", "")


configuracion = Configuracion()
