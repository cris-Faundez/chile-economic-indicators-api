from datetime import date
from decimal import Decimal
from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Indicator(Base):
    __tablename__ = "indicadores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    unidad_medida: Mapped[str] = mapped_column(String(50), nullable=False)

    valores: Mapped[list["IndicatorValue"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )


class IndicatorValue(Base):
    __tablename__ = "valores"
    __table_args__ = (
        UniqueConstraint("indicador_id", "fecha", name="uq_indicador_fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    indicador_id: Mapped[int] = mapped_column(
        ForeignKey("indicadores.id", ondelete="CASCADE"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    indicador: Mapped["Indicator"] = relationship(back_populates="valores")
