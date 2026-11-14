"""Contratos de dados entre módulos.

São a única interface entre `data/`, `engine/` e `app/`. Mudar um campo aqui
obriga a actualizar a fixture correspondente em `fixtures/`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Colunas do contrato ClimateDaily (DataFrame com índice de datas diárias).
CLIMATE_COLUMNS: tuple[str, ...] = (
    "p_mm",       # precipitação, mm/dia
    "tmax_c",     # temperatura máxima, °C
    "tmin_c",     # temperatura mínima, °C
    "tmean_c",    # temperatura média, °C
    "rh_pct",     # humidade relativa, %
    "wind_ms",    # vento a 2 m, m/s
    "rad_mj",     # radiação solar à superfície, MJ/m²/dia
    "et0_mm",     # evapotranspiração de referência, mm/dia (Hargreaves, data/features.py)
    "gwetroot",   # humidade da zona radicular, 0 a 1
    "season",     # ano agrícola (Julho a Junho) a que o dia pertence
    "source",     # origem dos dados, por exemplo "NASA POWER"
    "qc_flag",    # 0 = original, 1 = valor corrigido ou interpolado
)

# Os seis objectivos do score, pela ordem usada em toda a aplicação.
INDICATORS: tuple[str, ...] = (
    "agua",
    "solo",
    "resiliencia",
    "rendimento",
    "margem",
    "diversidade",
)

SCENARIOS: tuple[str, ...] = ("historico", "seco", "seco_parametrico", "quente", "favoravel")

STRATEGY_LABELS: tuple[str, ...] = (
    "monocultura",
    "convencional",
    "com_leguminosa",
    "recomendada",
)


@dataclass(frozen=True)
class Site:
    """Um local: ponto no mapa e data de sementeira assumida."""

    id: str
    name: str
    lat: float
    lon: float
    sow_month: int = 11
    sow_day: int = 15
    province: str | None = None
    current_crop: str = "milho"
    common_legume: str | None = None
    note: str | None = None


@dataclass
class SoilProfile:
    """Solo da camada 0-30 cm num ponto."""

    lat: float
    lon: float
    ph: float | None = None
    soc_gkg: float | None = None       # carbono orgânico, g/kg
    n_gkg: float | None = None         # azoto total, g/kg
    clay_pct: float | None = None
    sand_pct: float | None = None
    silt_pct: float | None = None
    fc_vol: float | None = None        # capacidade de campo, m³/m³
    wp_vol: float | None = None        # ponto de emurchecimento, m³/m³
    texture: str | None = None         # classe de params/soil_defaults.yaml
    source: str = "desconhecida"
    uncertainty: dict[str, float] = field(default_factory=dict)

    @property
    def taw_mm_per_m(self) -> float | None:
        """Água disponível total por metro de solo, em mm/m."""
        if self.fc_vol is None or self.wp_vol is None:
            return None
        return 1000 * (self.fc_vol - self.wp_vol)


@dataclass(frozen=True)
class Crop:
    """Uma linha de params/crops.csv. Campos por preencher ficam a None."""

    crop_id: str
    name_pt: str
    family: str
    group: str
    is_legume: bool
    l_ini: int
    l_dev: int
    l_mid: int
    l_late: int
    kc_ini: float
    kc_mid: float
    kc_end: float
    ky: float
    ky_status: str = "hipotese"
    scientific: str | None = None
    zr_m: float | None = None
    p: float | None = None
    tmin: float | None = None
    topmin: float | None = None
    topmax: float | None = None
    tmax: float | None = None
    ph_min: float | None = None
    ph_max: float | None = None
    ndfa: float | None = None
    n_fix_kg_ha: float | None = None
    n_export_kg_t: float | None = None
    src_stages_kc: str | None = None
    src_n: str | None = None
    notes: str | None = None

    @property
    def cycle_days(self) -> int:
        return self.l_ini + self.l_dev + self.l_mid + self.l_late


@dataclass
class StrategyResult:
    """Resultado de uma rotação de três campanhas."""

    label: str                              # um de STRATEGY_LABELS
    sequence: list[str]                     # três crop_id
    score: float
    indicators: dict[str, float]            # chaves = INDICATORS, valores em [0, 1]
    raw: dict[str, object] = field(default_factory=dict)
    contributions_vs_baseline: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """O que o motor entrega à interface."""

    site: dict[str, object]
    scenario: str
    weights: dict[str, float]
    strategies: list[StrategyResult]
    explanation: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
