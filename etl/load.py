import logging
import os
import time
from datetime import date
from decimal import Decimal
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.database import Base, SessionLocal, engine
from app.models import Indicator, IndicatorValue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://mindicador.cl/api"
INDICATORS = ["uf", "dolar", "utm"]
MAX_RETRIES = 3


def fetch_year_data(client: httpx.Client, code: str, year: int) -> dict | None:
    url = f"{BASE_URL}/{code}/{year}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Intento %d/%d fallido para %s (%d): %s",
                attempt,
                MAX_RETRIES,
                code,
                year,
                exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2.0)
    logger.error(
        "No se pudo obtener datos de %s para el año %d tras %d intentos.",
        code,
        year,
        MAX_RETRIES,
    )
    return None


def upsert_indicator(db: Session, code: str, name: str, unit: str) -> Indicator:
    stmt = (
        pg_insert(Indicator)
        .values(codigo=code, nombre=name, unidad_medida=unit)
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    db.execute(stmt)
    db.commit()
    return db.scalar(select(Indicator).where(Indicator.codigo == code))


def load_values(db: Session, indicator_id: int, series: list[dict]) -> int:
    if not series:
        return 0

    records = [
        {
            "indicador_id": indicator_id,
            "fecha": date.fromisoformat(item["fecha"][:10]),
            "valor": Decimal(str(item["valor"])),
        }
        for item in series
        if item.get("fecha") and item.get("valor") is not None
    ]

    if not records:
        return 0

    stmt = (
        pg_insert(IndicatorValue)
        .values(records)
        .on_conflict_do_nothing(index_elements=["indicador_id", "fecha"])
        .returning(IndicatorValue.id)
    )
    inserted_ids = db.scalars(stmt).all()
    db.commit()
    return len(inserted_ids)


def run_etl(years: int = 3) -> None:
    Base.metadata.create_all(bind=engine)
    current_year = date.today().year
    target_years = list(range(current_year - years + 1, current_year + 1))
    headers = {"User-Agent": "MonitorIndicadoresChile/1.0"}

    with SessionLocal() as db, httpx.Client(headers=headers) as client:
        for code in INDICATORS:
            logger.info("Procesando indicador: %s", code)
            indicator_obj: Indicator | None = None
            total_inserted = 0

            for year in target_years:
                payload = fetch_year_data(client, code, year)
                if not payload:
                    continue

                if indicator_obj is None:
                    indicator_obj = upsert_indicator(
                        db=db,
                        code=code,
                        name=payload.get("nombre", code.upper()),
                        unit=payload.get("unidad_medida", "Pesos"),
                    )

                inserted = load_values(db, indicator_obj.id, payload.get("serie", []))
                total_inserted += inserted

            logger.info(
                "Indicador %s finalizado. Nuevos registros insertados: %d",
                code,
                total_inserted,
            )


if __name__ == "__main__":
    years_env = int(os.getenv("ETL_YEARS", "3"))
    run_etl(years=years_env)
