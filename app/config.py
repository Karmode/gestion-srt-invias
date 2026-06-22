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


configuracion = Configuracion()
