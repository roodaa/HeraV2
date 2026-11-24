"""Service de calcul des émissions CO2."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facteur_emission import (
    FacteurEmissionElectricite,
    FacteurEmissionMateriel,
    FacteurEmissionNacres,
    FacteurEmissionTransport,
)
from app.models.materiel import TypeMateriel
from app.models.mission import ModeTransport


# Facteur par défaut pour les achats sans code NACRES (moyenne ADEME)
DEFAULT_FACTEUR_ACHAT = Decimal("0.5")  # kgCO2/€

# Facteur électricité France par défaut (kgCO2/kWh)
DEFAULT_FACTEUR_ELECTRICITE = Decimal("0.0569")


class CO2Service:
    """Service pour les calculs d'impact carbone."""

    # Cache des facteurs d'émission (en mémoire)
    _facteurs_transport_cache: dict[str, Decimal] = {}
    _facteurs_nacres_cache: dict[str, tuple[Decimal, str]] = {}  # (facteur, libelle)
    _facteurs_materiel_cache: dict[str, dict] = {}  # {impact_fabrication, conso_kwh, duree_vie}
    _facteur_electricite_cache: Decimal | None = None

    @classmethod
    async def get_facteur_transport(
        cls,
        db: AsyncSession,
        mode_transport: ModeTransport | str,
    ) -> Decimal:
        """
        Récupère le facteur d'émission pour un mode de transport.

        Args:
            db: Session de base de données
            mode_transport: Mode de transport

        Returns:
            Facteur en kgCO2/km
        """
        mode = mode_transport.value if isinstance(mode_transport, ModeTransport) else mode_transport

        # Vérifie le cache
        if mode in cls._facteurs_transport_cache:
            return cls._facteurs_transport_cache[mode]

        # Requête en base
        stmt = select(FacteurEmissionTransport).where(
            FacteurEmissionTransport.mode_transport == mode,
            FacteurEmissionTransport.is_active == True,
        )
        facteur = (await db.execute(stmt)).scalar_one_or_none()

        if facteur:
            cls._facteurs_transport_cache[mode] = facteur.facteur_kg_par_km
            return facteur.facteur_kg_par_km

        # Valeur par défaut si non trouvé
        return Decimal("0")

    @classmethod
    async def calculer_impact_etape(
        cls,
        db: AsyncSession,
        mode_transport: ModeTransport | str,
        distance_km: Decimal,
    ) -> Decimal:
        """
        Calcule l'impact CO2 d'une étape.

        Args:
            db: Session de base de données
            mode_transport: Mode de transport
            distance_km: Distance en km

        Returns:
            Impact en kgCO2
        """
        facteur = await cls.get_facteur_transport(db, mode_transport)
        return (distance_km * facteur).quantize(Decimal("0.001"))

    @classmethod
    async def calculer_impact_mission(
        cls,
        db: AsyncSession,
        etapes: list[dict],
        type_mission: str = "aller_retour",
    ) -> tuple[Decimal, Decimal, list[Decimal]]:
        """
        Calcule l'impact CO2 total d'une mission.

        Args:
            db: Session de base de données
            etapes: Liste des étapes avec mode_transport et distance_km
            type_mission: Type de mission (aller_simple ou aller_retour)

        Returns:
            Tuple (distance_totale, impact_total, impacts_par_etape)
        """
        distance_totale = Decimal("0")
        impact_total = Decimal("0")
        impacts_par_etape = []

        for etape in etapes:
            distance = Decimal(str(etape["distance_km"]))
            impact = await cls.calculer_impact_etape(
                db,
                etape["mode_transport"],
                distance,
            )

            distance_totale += distance
            impact_total += impact
            impacts_par_etape.append(impact)

        # Double pour aller-retour
        if type_mission == "aller_retour":
            distance_totale *= 2
            impact_total *= 2
            impacts_par_etape = [impact * 2 for impact in impacts_par_etape]

        return (
            distance_totale.quantize(Decimal("0.01")),
            impact_total.quantize(Decimal("0.001")),
            impacts_par_etape,
        )

    @classmethod
    async def preload_facteurs_transport(cls, db: AsyncSession) -> None:
        """
        Précharge tous les facteurs de transport en cache.
        Utile au démarrage de l'application.
        """
        stmt = select(FacteurEmissionTransport).where(
            FacteurEmissionTransport.is_active == True
        )
        result = await db.execute(stmt)
        facteurs = result.scalars().all()

        for facteur in facteurs:
            cls._facteurs_transport_cache[facteur.mode_transport] = facteur.facteur_kg_par_km

    @classmethod
    def clear_cache(cls) -> None:
        """Vide le cache des facteurs."""
        cls._facteurs_transport_cache.clear()
        cls._facteurs_nacres_cache.clear()
        cls._facteurs_materiel_cache.clear()
        cls._facteur_electricite_cache = None

    # ==================== Méthodes pour les achats ====================

    @classmethod
    async def get_facteur_nacres(
        cls,
        db: AsyncSession,
        code_nacres: str,
    ) -> tuple[Decimal, str | None]:
        """
        Récupère le facteur d'émission pour un code NACRES.

        Args:
            db: Session de base de données
            code_nacres: Code NACRES

        Returns:
            Tuple (facteur en kgCO2/€, libellé)
        """
        # Vérifie le cache
        if code_nacres in cls._facteurs_nacres_cache:
            return cls._facteurs_nacres_cache[code_nacres]

        # Requête en base
        stmt = select(FacteurEmissionNacres).where(
            FacteurEmissionNacres.code_nacres == code_nacres,
            FacteurEmissionNacres.is_active == True,
        )
        facteur = (await db.execute(stmt)).scalar_one_or_none()

        if facteur:
            result = (facteur.facteur_kg_par_euro, facteur.libelle)
            cls._facteurs_nacres_cache[code_nacres] = result
            return result

        # Valeur par défaut si non trouvé
        return (DEFAULT_FACTEUR_ACHAT, None)

    @classmethod
    async def calculer_impact_achat(
        cls,
        db: AsyncSession,
        montant_euros: Decimal,
        code_nacres: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """
        Calcule l'impact CO2 d'un achat.

        Args:
            db: Session de base de données
            montant_euros: Montant de l'achat en euros
            code_nacres: Code NACRES (optionnel)

        Returns:
            Tuple (impact_co2_kg, facteur_utilise)
        """
        if code_nacres:
            facteur, _ = await cls.get_facteur_nacres(db, code_nacres)
        else:
            facteur = DEFAULT_FACTEUR_ACHAT

        impact = (montant_euros * facteur).quantize(Decimal("0.001"))
        return (impact, facteur)

    @classmethod
    async def preload_facteurs_nacres(cls, db: AsyncSession) -> None:
        """
        Précharge tous les facteurs NACRES en cache.
        Utile au démarrage de l'application.
        """
        stmt = select(FacteurEmissionNacres).where(
            FacteurEmissionNacres.is_active == True
        )
        result = await db.execute(stmt)
        facteurs = result.scalars().all()

        for facteur in facteurs:
            cls._facteurs_nacres_cache[facteur.code_nacres] = (
                facteur.facteur_kg_par_euro,
                facteur.libelle,
            )

    @classmethod
    async def get_all_codes_nacres(
        cls,
        db: AsyncSession,
    ) -> list[dict]:
        """
        Récupère tous les codes NACRES disponibles.

        Returns:
            Liste des codes NACRES avec leurs libellés et facteurs
        """
        stmt = select(FacteurEmissionNacres).where(
            FacteurEmissionNacres.is_active == True
        ).order_by(FacteurEmissionNacres.code_nacres)

        result = await db.execute(stmt)
        facteurs = result.scalars().all()

        return [
            {
                "code": f.code_nacres,
                "libelle": f.libelle,
                "facteur_kg_par_euro": float(f.facteur_kg_par_euro),
            }
            for f in facteurs
        ]

    # ==================== Méthodes pour le matériel ====================

    @classmethod
    async def get_facteur_electricite(cls, db: AsyncSession, pays: str = "FR") -> Decimal:
        """
        Récupère le facteur d'émission de l'électricité.

        Args:
            db: Session de base de données
            pays: Code pays (défaut: FR)

        Returns:
            Facteur en kgCO2/kWh
        """
        if cls._facteur_electricite_cache is not None:
            return cls._facteur_electricite_cache

        stmt = select(FacteurEmissionElectricite).where(
            FacteurEmissionElectricite.pays == pays,
            FacteurEmissionElectricite.is_active == True,
        )
        facteur = (await db.execute(stmt)).scalar_one_or_none()

        if facteur:
            cls._facteur_electricite_cache = facteur.facteur_kg_par_kwh
            return facteur.facteur_kg_par_kwh

        return DEFAULT_FACTEUR_ELECTRICITE

    @classmethod
    async def get_facteur_materiel(
        cls,
        db: AsyncSession,
        type_materiel: TypeMateriel | str,
    ) -> dict:
        """
        Récupère les facteurs d'émission pour un type de matériel.

        Args:
            db: Session de base de données
            type_materiel: Type de matériel

        Returns:
            Dict avec impact_fabrication_kg, consommation_kwh_annuelle, duree_vie_standard
        """
        type_str = type_materiel.value if isinstance(type_materiel, TypeMateriel) else type_materiel

        # Vérifie le cache
        if type_str in cls._facteurs_materiel_cache:
            return cls._facteurs_materiel_cache[type_str]

        # Requête en base
        stmt = select(FacteurEmissionMateriel).where(
            FacteurEmissionMateriel.type_materiel == type_str,
            FacteurEmissionMateriel.is_active == True,
        )
        facteur = (await db.execute(stmt)).scalar_one_or_none()

        if facteur:
            result = {
                "impact_fabrication_kg": facteur.impact_fabrication_kg,
                "consommation_kwh_annuelle": facteur.consommation_kwh_annuelle,
                "duree_vie_standard": facteur.duree_vie_standard,
            }
            cls._facteurs_materiel_cache[type_str] = result
            return result

        # Valeurs par défaut si non trouvé
        return {
            "impact_fabrication_kg": Decimal("100"),
            "consommation_kwh_annuelle": Decimal("50"),
            "duree_vie_standard": 5,
        }

    @classmethod
    async def calculer_impact_materiel(
        cls,
        db: AsyncSession,
        type_materiel: TypeMateriel | str,
        consommation_kwh: Decimal | None = None,
        impact_fabrication: Decimal | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calcule l'impact CO2 d'un matériel.

        Args:
            db: Session de base de données
            type_materiel: Type de matériel
            consommation_kwh: Consommation annuelle (optionnel, sinon valeur standard)
            impact_fabrication: Impact fabrication (optionnel, sinon valeur standard)

        Returns:
            Tuple (impact_fabrication_kg, consommation_kwh_annuelle, impact_usage_annuel_kg)
        """
        # Récupère les facteurs standards
        facteurs = await cls.get_facteur_materiel(db, type_materiel)
        facteur_elec = await cls.get_facteur_electricite(db)

        # Utilise les valeurs fournies ou les valeurs standards
        fabrication = impact_fabrication if impact_fabrication is not None else facteurs["impact_fabrication_kg"]
        conso = consommation_kwh if consommation_kwh is not None else facteurs["consommation_kwh_annuelle"]

        # Calcul impact usage = consommation × facteur électricité
        if conso:
            impact_usage = (conso * facteur_elec).quantize(Decimal("0.001"))
        else:
            impact_usage = Decimal("0")

        return (
            Decimal(str(fabrication)).quantize(Decimal("0.001")),
            Decimal(str(conso)) if conso else None,
            impact_usage,
        )

    @classmethod
    async def get_all_types_materiel(cls, db: AsyncSession) -> list[dict]:
        """
        Récupère tous les types de matériel avec leurs facteurs.

        Returns:
            Liste des types avec leurs facteurs d'émission
        """
        stmt = select(FacteurEmissionMateriel).where(
            FacteurEmissionMateriel.is_active == True
        ).order_by(FacteurEmissionMateriel.type_materiel)

        result = await db.execute(stmt)
        facteurs = result.scalars().all()

        return [
            {
                "type_materiel": f.type_materiel,
                "impact_fabrication_kg": float(f.impact_fabrication_kg),
                "consommation_kwh_annuelle": float(f.consommation_kwh_annuelle) if f.consommation_kwh_annuelle else None,
                "duree_vie_standard": f.duree_vie_standard,
            }
            for f in facteurs
        ]

    @classmethod
    async def preload_facteurs_materiel(cls, db: AsyncSession) -> None:
        """
        Précharge tous les facteurs matériel en cache.
        Utile au démarrage de l'application.
        """
        stmt = select(FacteurEmissionMateriel).where(
            FacteurEmissionMateriel.is_active == True
        )
        result = await db.execute(stmt)
        facteurs = result.scalars().all()

        for f in facteurs:
            cls._facteurs_materiel_cache[f.type_materiel] = {
                "impact_fabrication_kg": f.impact_fabrication_kg,
                "consommation_kwh_annuelle": f.consommation_kwh_annuelle,
                "duree_vie_standard": f.duree_vie_standard,
            }

        # Précharge aussi le facteur électricité
        await cls.get_facteur_electricite(db)
