from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import csv
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(
    title="PasseportEtudiant API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
api_router = APIRouter(prefix="/api")


# ============== MODELS ==============
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class School(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    hall_id: str
    name: str
    type: str
    initials: str
    qr_token: str


class Consents(BaseModel):
    l: bool = False  # Contenus personnalisés l'Étudiant  # noqa: E741
    d: bool = False  # Diplomeo
    c: bool = False  # Partenaires
    e: bool = False  # Enquêtes


class Student(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    serial: str
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    emoji: str = "🧑"
    classe: str = "Non renseigné"
    filieres: List[str] = Field(default_factory=list)
    formation: List[str] = Field(default_factory=list)
    nat: str = "NON SPÉCIFIÉE"
    dob_short: str = "—"
    sex: str = "—"
    lieu: str = "—"
    expire: str = "15/04/2031"
    consents: Consents = Field(default_factory=Consents)
    class_code: Optional[str] = None
    is_demo: bool = False
    is_anonymous: bool = False  # Théo case
    is_guest: bool = False
    guest_claimed: bool = False
    claimed_at: Optional[str] = None
    # Engagement signals (D2 / D3)
    scan_exposant: bool = False
    email_opened: bool = False
    clicked_reco: bool = False
    returned_site: bool = False
    created_at: str = Field(default_factory=now_iso)


class StudentCreate(BaseModel):
    name: str
    emoji: str = "🧑"
    classe: str = "Non renseigné"
    filieres: List[str] = Field(default_factory=list)
    formation: List[str] = Field(default_factory=list)
    class_code: Optional[str] = None


class GuestClaim(BaseModel):
    first_name: str
    last_name: str = ""
    email: str


class StudentUpdate(BaseModel):
    emoji: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    classe: Optional[str] = None
    filieres: Optional[List[str]] = None
    formation: Optional[List[str]] = None
    consents: Optional[Consents] = None
    scan_exposant: Optional[bool] = None
    email_opened: Optional[bool] = None
    clicked_reco: Optional[bool] = None
    returned_site: Optional[bool] = None


class Stamp(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    school_id: str
    hall_id: str
    school_name: str
    time_label: str
    rating: Optional[int] = None  # 1-5, given by student after visit
    timestamp: str = Field(default_factory=now_iso)


class StampCreate(BaseModel):
    student_id: str
    qr_token: str


class StampRating(BaseModel):
    rating: int  # 1-5


class ClassRoom(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str
    teacher_name: str
    school_name: str
    created_at: str = Field(default_factory=now_iso)


class ClassCreate(BaseModel):
    teacher_name: str
    school_name: str


# ============== SEED ==============
HALLS_SEED = [
    {"id": "i", "label": "Ingénierie & Numérique", "color": "#1A237E"},
    {"id": "c", "label": "Commerce & Marketing", "color": "#E3000B"},
    {"id": "s", "label": "Santé & Universités", "color": "#6D28D9"},
    {"id": "a", "label": "Arts & Tourisme", "color": "#db2777"},
    {"id": "k", "label": "Orientation & Prépa", "color": "#047857"},
]

# Filières → hall mapping (used for D3 pertinence + recommendations)
FILIERE_TO_HALL = {
    "Ingénierie": "i",
    "Numérique": "i",
    "Commerce": "c",
    "Sciences Po": "s",
    "Santé": "s",
    "Arts": "a",
    "Droit": "s",
}

# Keywords per filière used to match against school type descriptions
FILIERE_KEYWORDS = {
    "Ingénierie": ["ingénieurs", "ingénierie", "ingénieur"],
    "Numérique":  ["numérique", "informatique", "digital", "jeu vidéo", "cybersécurité", "tech"],
    "Commerce":   ["commerce", "management", "business", "marketing", "gestion", "finance", "communication", "logistique"],
    "Sciences Po": ["sciences po", "iep", "politique", "social"],
    "Santé":      ["santé", "médecine", "pharmacie", "paramédical", "ostéopathie", "kiné", "maïeutique", "chiro"],
    "Arts":       ["art", "design", "cinéma", "animation", "hôtellerie", "tourisme", "luxe", "audiovisuel"],
    "Droit":      ["droit", "juridique"],
}

# Filières considered premium (D4 commercial value bonus)
PREMIUM_FILIERES = {"Commerce", "Ingénierie", "Sciences Po", "Numérique"}
DEMO_QR_STUDENT_ID = "demo-lucas"
DEMO_QR_BOOTHS = [
    {"school_id": "s2", "label": "Albert School booth"},
    {"school_id": "s4", "label": "EPITA booth"},
    {"school_id": "s100", "label": "Mines booth"},
]

SCHOOLS_SEED = [
    # Ingénierie & Numérique (26)
    {"id": "s1",  "hall_id": "i", "name": "89 — École Supérieure du Numérique", "type": "Informatique & Numérique · Paris", "initials": "89"},
    {"id": "s2",  "hall_id": "i", "name": "Albert School / Mines Paris - PSL", "type": "Ingénieurs & Management · Paris", "initials": "AS"},
    {"id": "s100", "hall_id": "i", "name": "Mines Paris - PSL", "type": "Grande ecole d'ingenieurs - Paris", "initials": "MP"},
    {"id": "s3",  "hall_id": "i", "name": "CESI École d'Ingénieurs", "type": "École d'ingénieurs · Multi-sites", "initials": "CE"},
    {"id": "s4",  "hall_id": "i", "name": "Concours Advance (EPITA·ESME·IPSA)", "type": "Concours ingénieurs post-bac · Paris", "initials": "CA"},
    {"id": "s5",  "hall_id": "i", "name": "EEMI", "type": "Métiers du digital · Paris", "initials": "EE"},
    {"id": "s6",  "hall_id": "i", "name": "EFREI — Digital & Management", "type": "École ingénieurs numérique · Villejuif", "initials": "EF"},
    {"id": "s7",  "hall_id": "i", "name": "Efrei Panthéon-Assas Université", "type": "École ingénieurs · Villejuif", "initials": "EU"},
    {"id": "s8",  "hall_id": "i", "name": "EFRITS", "type": "École de la Tech · Paris", "initials": "ER"},
    {"id": "s9",  "hall_id": "i", "name": "EIGSI", "type": "Ingénieurs généralistes · La Rochelle", "initials": "EI"},
    {"id": "s10", "hall_id": "i", "name": "EPITECH", "type": "Informatique · Paris & Multi-sites", "initials": "ET"},
    {"id": "s11", "hall_id": "i", "name": "EPF Engineering School", "type": "École d'ingénieurs · Sceaux", "initials": "EP"},
    {"id": "s12", "hall_id": "i", "name": "ESIEA", "type": "Ingénieurs numérique · Paris", "initials": "EA"},
    {"id": "s13", "hall_id": "i", "name": "ESIGELEC", "type": "Ingénieurs généraliste · Rouen", "initials": "EG"},
    {"id": "s14", "hall_id": "i", "name": "ESITC Paris", "type": "Ingénieurs construction · Marne-la-Vallée", "initials": "EC"},
    {"id": "s15", "hall_id": "i", "name": "ESME", "type": "Ingénieurs généraliste · Paris", "initials": "SM"},
    {"id": "s16", "hall_id": "i", "name": "ESTACA — ISAE", "type": "Ingénieurs · Levallois-Perret", "initials": "EX"},
    {"id": "s17", "hall_id": "i", "name": "ESTP", "type": "Grande école ingénieurs · Cachan", "initials": "ST"},
    {"id": "s18", "hall_id": "i", "name": "Gaming Campus", "type": "Métiers du jeu vidéo · Paris", "initials": "GC"},
    {"id": "s19", "hall_id": "i", "name": "Guardia Cybersecurity School", "type": "Cybersécurité · Paris", "initials": "GU"},
    {"id": "s20", "hall_id": "i", "name": "IESF", "type": "Ingénieurs & Scientifiques de France", "initials": "IF"},
    {"id": "s21", "hall_id": "i", "name": "IIM", "type": "Numérique · Paris La Défense", "initials": "II"},
    {"id": "s22", "hall_id": "i", "name": "ISEP", "type": "Ingénieurs numérique · Paris", "initials": "IS"},
    {"id": "s23", "hall_id": "i", "name": "ISEL", "type": "École d'ingénieurs · Le Havre", "initials": "IL"},
    {"id": "s24", "hall_id": "i", "name": "SUPINFO", "type": "Informatique · Paris & Multi-sites", "initials": "SU"},
    {"id": "s25", "hall_id": "i", "name": "UniLaSalle", "type": "Ingénieurs · Rouen / Paris", "initials": "UL"},
    {"id": "s26", "hall_id": "i", "name": "École Polytechnique", "type": "Grande école · Palaiseau", "initials": "X"},

    # Commerce & Marketing (26)
    {"id": "s27", "hall_id": "c", "name": "Audencia", "type": "Grande école de commerce · Nantes", "initials": "AU"},
    {"id": "s28", "hall_id": "c", "name": "Concours Sésame", "type": "Concours écoles commerce post-bac", "initials": "CS"},
    {"id": "s29", "hall_id": "c", "name": "EDHEC Business School", "type": "Grande école · Lille / Nice", "initials": "ED"},
    {"id": "s30", "hall_id": "c", "name": "EFAP / ICART / EFJ", "type": "Communication & Journalisme · Paris", "initials": "EJ"},
    {"id": "s31", "hall_id": "c", "name": "EMLV", "type": "École de commerce · Paris La Défense", "initials": "EM"},
    {"id": "s32", "hall_id": "c", "name": "ESG Paris", "type": "École de commerce · Paris", "initials": "ES"},
    {"id": "s33", "hall_id": "c", "name": "European Business School", "type": "École de commerce · Paris", "initials": "EB"},
    {"id": "s34", "hall_id": "c", "name": "Excelia", "type": "École de commerce · La Rochelle / Tours", "initials": "EL"},
    {"id": "s35", "hall_id": "c", "name": "ICN Business School", "type": "École de commerce · Nancy", "initials": "IC"},
    {"id": "s36", "hall_id": "c", "name": "ICS Bégué", "type": "Gestion / Finance · Paris", "initials": "IB"},
    {"id": "s37", "hall_id": "c", "name": "Igensia RH", "type": "Management RH · Paris", "initials": "IG"},
    {"id": "s38", "hall_id": "c", "name": "Institut Assur Formation", "type": "Assurance & Finance · Paris", "initials": "IA"},
    {"id": "s39", "hall_id": "c", "name": "IMT Business School", "type": "École de commerce · Évry", "initials": "IM"},
    {"id": "s40", "hall_id": "c", "name": "IPAG Business School", "type": "École de commerce · Paris / Nice", "initials": "IP"},
    {"id": "s41", "hall_id": "c", "name": "ISC Paris", "type": "École de commerce · Paris", "initials": "SC"},
    {"id": "s42", "hall_id": "c", "name": "ISCOM", "type": "Communication & Publicité · Paris", "initials": "IO"},
    {"id": "s43", "hall_id": "c", "name": "ISEFAC Événementiel", "type": "Communication & Événementiel · Paris", "initials": "IE"},
    {"id": "s44", "hall_id": "c", "name": "ISEG Paris", "type": "Marketing & Communication · Paris", "initials": "IK"},
    {"id": "s45", "hall_id": "c", "name": "ISG International Business School", "type": "École de commerce · Paris", "initials": "IR"},
    {"id": "s46", "hall_id": "c", "name": "ISG Luxury Program", "type": "Commerce du luxe · Paris", "initials": "IX"},
    {"id": "s47", "hall_id": "c", "name": "ISG Sport Business Management", "type": "Sport Business · Paris", "initials": "IZ"},
    {"id": "s48", "hall_id": "c", "name": "ISTEC Business School", "type": "École de commerce · Paris", "initials": "IT"},
    {"id": "s49", "hall_id": "c", "name": "IÉSEG School of Management", "type": "Grande école · Lille / Paris", "initials": "IÉ"},
    {"id": "s50", "hall_id": "c", "name": "NEOMA Business School", "type": "Grande école · Reims / Rouen", "initials": "NE"},
    {"id": "s51", "hall_id": "c", "name": "Promotrans", "type": "Logistique & Transport · Paris", "initials": "PT"},
    {"id": "s52", "hall_id": "c", "name": "France Supply Chain", "type": "Supply Chain & Logistique · Paris", "initials": "FS"},

    # Santé & Universités (19)
    {"id": "s53", "hall_id": "s", "name": "ANEMF", "type": "Étudiants en médecine · National", "initials": "AN"},
    {"id": "s54", "hall_id": "s", "name": "Antémed Epsilon", "type": "Prépa PASS / LAS · Paris", "initials": "AE"},
    {"id": "s55", "hall_id": "s", "name": "Assoc. Étudiants en Pharmacie", "type": "Pharmacie · National", "initials": "PH"},
    {"id": "s56", "hall_id": "s", "name": "Assoc. Étudiants Sages-Femmes", "type": "Maïeutique · National", "initials": "SF"},
    {"id": "s57", "hall_id": "s", "name": "CPCM", "type": "Prépa santé PASS LAS · Paris", "initials": "CP"},
    {"id": "s58", "hall_id": "s", "name": "Diploma Santé", "type": "Santé & Paramédical · Paris", "initials": "DS"},
    {"id": "s59", "hall_id": "s", "name": "EO Paris", "type": "Ostéopathie · Paris", "initials": "EO"},
    {"id": "s60", "hall_id": "s", "name": "ESP — Psychologie Européenne", "type": "Psychologie · Paris", "initials": "PS"},
    {"id": "s61", "hall_id": "s", "name": "Faculté Médecine — Strasbourg", "type": "Médecine & Maïeutique · Strasbourg", "initials": "FM"},
    {"id": "s62", "hall_id": "s", "name": "FNEK", "type": "Kinésithérapie · National", "initials": "FK"},
    {"id": "s63", "hall_id": "s", "name": "IFEC Chiropraxie", "type": "Chiropraxie · Paris", "initials": "IF"},
    {"id": "s64", "hall_id": "s", "name": "Le Gall Conseil", "type": "Études de santé en Europe · Paris", "initials": "LG"},
    {"id": "s65", "hall_id": "s", "name": "Médisup Paris", "type": "Prépa études de santé · Paris", "initials": "MS"},
    {"id": "s66", "hall_id": "s", "name": "UNAFORIS", "type": "Social & Paramédical · Paris", "initials": "UA"},
    {"id": "s67", "hall_id": "s", "name": "Collège de Droit — Sorbonne", "type": "Université · Droit · Paris", "initials": "CD"},
    {"id": "s68", "hall_id": "s", "name": "EFLV — Pôle Léonard de Vinci", "type": "Université · Paris La Défense", "initials": "EV"},
    {"id": "s69", "hall_id": "s", "name": "IUT de Villetaneuse", "type": "IUT · Villetaneuse", "initials": "IV"},
    {"id": "s70", "hall_id": "s", "name": "ORACLE — 14 Universités IDF", "type": "Universités Île-de-France", "initials": "OR"},
    {"id": "s71", "hall_id": "s", "name": "Université Catholique de Lille", "type": "Université catholique · Lille", "initials": "UC"},

    # Arts & Tourisme (9)
    {"id": "s72", "hall_id": "a", "name": "Autograf Design", "type": "Art & Design · Paris", "initials": "AG"},
    {"id": "s73", "hall_id": "a", "name": "E-Artsup", "type": "Design & Industries créatives · Paris", "initials": "AR"},
    {"id": "s74", "hall_id": "a", "name": "EMC", "type": "Cinéma · 3D · Animation · VFX · Paris", "initials": "EC"},
    {"id": "s75", "hall_id": "a", "name": "ESDMA", "type": "Art / Design / Audiovisuel · Montpellier", "initials": "ED"},
    {"id": "s76", "hall_id": "a", "name": "Orélia School", "type": "Art & Design · Paris", "initials": "OL"},
    {"id": "s77", "hall_id": "a", "name": "EPMT", "type": "Hôtellerie · Restauration · Paris", "initials": "EP"},
    {"id": "s78", "hall_id": "a", "name": "Eugenia School", "type": "Tourisme & Hôtellerie · Paris", "initials": "EU"},
    {"id": "s79", "hall_id": "a", "name": "Ferrières Hospitality & Luxury", "type": "Hôtellerie & Luxe · Ferrières-en-Brie", "initials": "FE"},
    {"id": "s80", "hall_id": "a", "name": "Vatel", "type": "Hôtellerie & Tourisme · Paris", "initials": "VA"},

    # Orientation & Prépa (19)
    {"id": "s81", "hall_id": "k", "name": "APECITA", "type": "Orientation agricole & environnement", "initials": "AP"},
    {"id": "s82", "hall_id": "k", "name": "APEL de l'Essonne", "type": "Orientation / Parents · Essonne", "initials": "AL"},
    {"id": "s83", "hall_id": "k", "name": "Armée de Terre", "type": "Armées & Défense · National", "initials": "AT"},
    {"id": "s84", "hall_id": "k", "name": "CFA Trajectoire", "type": "Apprentissage · Île-de-France", "initials": "CT"},
    {"id": "s85", "hall_id": "k", "name": "Gendarmerie Nationale", "type": "Armées & Défense · National", "initials": "GN"},
    {"id": "s86", "hall_id": "k", "name": "Gen' Club", "type": "Vie étudiante & Orientation · Paris", "initials": "GE"},
    {"id": "s87", "hall_id": "k", "name": "Groupe Aurlom", "type": "Prépa concours & examens · Paris", "initials": "GA"},
    {"id": "s88", "hall_id": "k", "name": "Groupe Ipésup", "type": "Prépa concours · Paris", "initials": "GI"},
    {"id": "s89", "hall_id": "k", "name": "Jai20enMaths", "type": "Prépa maths · En ligne / Paris", "initials": "JM"},
    {"id": "s90", "hall_id": "k", "name": "Lycée de Cachan", "type": "Prépa concours · Cachan", "initials": "LC"},
    {"id": "s91", "hall_id": "k", "name": "Marine Nationale", "type": "Armées & Défense · National", "initials": "MN"},
    {"id": "s92", "hall_id": "k", "name": "Mission Grande École", "type": "Conseil orientation · Paris", "initials": "MG"},
    {"id": "s93", "hall_id": "k", "name": "OPCO Atlas", "type": "Formation professionnelle · Paris", "initials": "OA"},
    {"id": "s94", "hall_id": "k", "name": "Police Nationale", "type": "Armées & Défense · National", "initials": "PN"},
    {"id": "s95", "hall_id": "k", "name": "Prépa Prévision", "type": "Prépa concours · Paris", "initials": "PP"},
    {"id": "s96", "hall_id": "k", "name": "Prépa Concours Proodos", "type": "Prépa concours · Paris", "initials": "PC"},
    {"id": "s97", "hall_id": "k", "name": "Terraskola", "type": "Prépa concours · Paris", "initials": "TK"},
    {"id": "s98", "hall_id": "k", "name": "TonAvenir", "type": "Conseil en orientation · Paris", "initials": "TV"},
    {"id": "s99", "hall_id": "k", "name": "Youth ID", "type": "Vie étudiante & Orientation · Paris", "initials": "YI"},
]


async def seed_database():
    # Schools — re-seed if count doesn't match (handles schema updates)
    school_count = await db.schools.count_documents({})
    if school_count != len(SCHOOLS_SEED):
        await db.schools.delete_many({})
        docs = []
        for s in SCHOOLS_SEED:
            doc = {**s, "qr_token": f"STAND-{s['id'].upper()}-{secrets.token_hex(3).upper()}"}
            docs.append(doc)
        await db.schools.insert_many(docs)
        logger.info(f"Seeded {len(docs)} schools (was {school_count})")

    # Demo class
    if await db.classes.count_documents({"code": "PROF2026"}) == 0:
        await db.classes.insert_one({
            "id": str(uuid.uuid4()),
            "code": "PROF2026",
            "teacher_name": "M. Bernard",
            "school_name": "Lycée Henri-IV · Terminale S3",
            "created_at": now_iso(),
        })
        logger.info("Seeded demo class PROF2026")

    # Demo student: Lucas
    if await db.students.count_documents({"id": "demo-lucas"}) == 0:
        lucas = {
            "id": "demo-lucas",
            "serial": "SAL-2026-04721",
            "name": "Lucas Martin",
            "emoji": "🎓",
            "classe": "Terminale générale",
            "filieres": ["Ingénierie", "Numérique"],
            "formation": ["École d'ingénieurs"],
            "nat": "FRANÇAISE",
            "dob_short": "12/03/2008",
            "sex": "M",
            "lieu": "Paris (75)",
            "expire": "15/04/2031",
            "consents": {"l": True, "d": True, "c": True, "e": False},
            "class_code": "PROF2026",
            "is_demo": True,
            "is_anonymous": False,
            "scan_exposant": True,
            "email_opened": True,
            "clicked_reco": True,
            "returned_site": False,
            "created_at": now_iso(),
        }
        await db.students.insert_one(lucas)
        # Lucas's stamps with new IDs
        lucas_stamps = ["s1", "s6", "s10", "c2"]
        for sid in lucas_stamps:
            sc = await db.schools.find_one({"id": sid}, {"_id": 0})
            if not sc:
                continue
            await db.stamps.insert_one({
                "id": str(uuid.uuid4()),
                "student_id": "demo-lucas",
                "school_id": sc["id"],
                "hall_id": sc["hall_id"],
                "school_name": sc["name"],
                "time_label": f"{14 + secrets.randbelow(4)}h{str(secrets.randbelow(60)).zfill(2)}",
                "timestamp": now_iso(),
            })

    # Demo student: Théo (anonyme)
    if await db.students.count_documents({"id": "demo-theo"}) == 0:
        theo = {
            "id": "demo-theo",
            "serial": "—",
            "name": "Théo",
            "emoji": "👥",
            "classe": "—",
            "filieres": [],
            "formation": [],
            "nat": "—",
            "dob_short": "—",
            "sex": "—",
            "lieu": "—",
            "expire": "—",
            "consents": {"l": False, "d": False, "c": False, "e": False},
            "class_code": None,
            "is_demo": True,
            "is_anonymous": True,
            "created_at": now_iso(),
        }
        await db.students.insert_one(theo)

    # Second demo class for leaderboard
    if await db.classes.count_documents({"code": "PROF2026B"}) == 0:
        await db.classes.insert_one({
            "id": str(uuid.uuid4()),
            "code": "PROF2026B",
            "teacher_name": "Mme Durand",
            "school_name": "Lycée Louis-le-Grand · Terminale S1",
            "created_at": now_iso(),
        })

    # Rich seed students (for vivid analytics + leaderboard on first launch)
    fixtures = [
        # class PROF2026 (Henri-IV)
        {"id": "demo-emma", "name": "Emma Lefebvre", "emoji": "🧑‍🎓", "classe": "Terminale générale",
         "filieres": ["Commerce", "Droit"], "formation": ["Grande École", "IEP"],
         "consents": {"l": True, "d": True, "c": False, "e": True},
         "class_code": "PROF2026",
         "stamps": ["s15", "s16", "s17", "c1"],
         "scan_exposant": True, "email_opened": True, "clicked_reco": False, "returned_site": False},
        {"id": "demo-nadia", "name": "Nadia Rahmani", "emoji": "👩‍🎓", "classe": "Terminale générale",
         "filieres": ["Santé", "Sciences Po"], "formation": ["Université", "IEP"],
         "consents": {"l": True, "d": True, "c": True, "e": False},
         "class_code": "PROF2026",
         "stamps": ["s23", "s30", "c1", "c4"],
         "scan_exposant": True, "email_opened": True, "clicked_reco": True, "returned_site": False},
        {"id": "demo-hugo", "name": "Hugo Lambert", "emoji": "👨‍🎓", "classe": "Terminale générale",
         "filieres": ["Ingénierie", "Numérique"], "formation": ["École d'ingénieurs"],
         "consents": {"l": True, "d": False, "c": False, "e": False},
         "class_code": "PROF2026",
         "stamps": ["s1", "s11"],
         "scan_exposant": False, "email_opened": False, "clicked_reco": False, "returned_site": False},
        # class PROF2026B (Louis-le-Grand)
        {"id": "demo-sarah", "name": "Sarah Mercier", "emoji": "👩", "classe": "Terminale générale",
         "filieres": ["Ingénierie", "Numérique"], "formation": ["École d'ingénieurs", "Prépa CPGE"],
         "consents": {"l": True, "d": True, "c": True, "e": True},
         "class_code": "PROF2026B",
         "stamps": ["s1", "s2", "s3", "s4", "s11", "s12", "c1", "c2"],
         "scan_exposant": True, "email_opened": True, "clicked_reco": True, "returned_site": True},
        {"id": "demo-malik", "name": "Malik Benali", "emoji": "😎", "classe": "Terminale générale",
         "filieres": ["Commerce"], "formation": ["Grande École"],
         "consents": {"l": True, "d": True, "c": True, "e": False},
         "class_code": "PROF2026B",
         "stamps": ["s15", "s16", "s17", "s19", "c3"],
         "scan_exposant": True, "email_opened": True, "clicked_reco": False, "returned_site": True},
        {"id": "demo-lea", "name": "Léa Dupont", "emoji": "🤓", "classe": "Terminale générale",
         "filieres": ["Arts"], "formation": ["Université"],
         "consents": {"l": True, "d": False, "c": False, "e": False},
         "class_code": "PROF2026B",
         "stamps": ["s31"],
         "scan_exposant": False, "email_opened": False, "clicked_reco": False, "returned_site": False},
    ]

    for f in fixtures:
        if await db.students.count_documents({"id": f["id"]}) > 0:
            continue
        student_doc = {
            "id": f["id"],
            "serial": f"SAL-2026-{secrets.randbelow(90000) + 10000}",
            "name": f["name"],
            "emoji": f["emoji"],
            "classe": f["classe"],
            "filieres": f["filieres"],
            "formation": f["formation"],
            "nat": "FRANÇAISE",
            "dob_short": "—",
            "sex": "—",
            "lieu": "—",
            "expire": "15/04/2031",
            "consents": f["consents"],
            "class_code": f["class_code"],
            "is_demo": True,
            "is_anonymous": False,
            "scan_exposant": f.get("scan_exposant", False),
            "email_opened": f.get("email_opened", False),
            "clicked_reco": f.get("clicked_reco", False),
            "returned_site": f.get("returned_site", False),
            "created_at": now_iso(),
        }
        await db.students.insert_one(student_doc)
        # seed stamps
        for sid in f["stamps"]:
            sc = await db.schools.find_one({"id": sid}, {"_id": 0})
            if not sc:
                continue
            await db.stamps.insert_one({
                "id": str(uuid.uuid4()),
                "student_id": f["id"],
                "school_id": sc["id"],
                "hall_id": sc["hall_id"],
                "school_name": sc["name"],
                "time_label": f"{14 + secrets.randbelow(4)}h{str(secrets.randbelow(60)).zfill(2)}",
                "timestamp": now_iso(),
            })


# ============== HELPERS ==============
def clean_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


def qr_payload_to_school_lookup(value: str) -> str:
    payload = (value or "").strip()
    if "/scan/" not in payload:
        return payload
    try:
        parsed = urlparse(payload)
        path = parsed.path or payload
    except Exception:
        path = payload
    marker = "/scan/"
    if marker not in path:
        return payload
    return path.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]


def _filiere_type_score(filieres: list, school_type: str) -> int:
    """0-50pts: how well school's type description matches student's declared filières.
    Points are distributed equally across declared filières — matching all gives 50pts,
    matching only one out of two gives 25pts, etc. This creates individual scores per school."""
    if not filieres:
        return 0
    type_lower = school_type.lower()
    pts_per_filiere = 50 / len(filieres)
    total = sum(
        pts_per_filiere
        for f in filieres
        if f in FILIERE_KEYWORDS and any(kw in type_lower for kw in FILIERE_KEYWORDS[f])
    )
    return min(50, round(total))


def _type_similarity(type_a: str, type_b: str) -> float:
    """Jaccard similarity on description keywords (before ' · ').
    Returns 0-1. Used to weight rating signal per recommended school individually."""
    import re
    def keywords(t: str):
        desc = t.split(" · ")[0].lower() if " · " in t else t.lower()
        words = set(re.split(r"[\s&/\-,()]+", desc))
        return {w for w in words if len(w) > 2}
    kw_a = keywords(type_a)
    kw_b = keywords(type_b)
    if not kw_a or not kw_b:
        return 0.0
    return len(kw_a & kw_b) / len(kw_a | kw_b)


def compute_score(stamp_count: int, consents_count: int, filieres_count: int) -> int:
    # Legacy wrapper — passes minimal context, D3 will be 0
    breakdown = score_breakdown(
        stamp_count=stamp_count,
        consents={},
        filieres=[],
        school_stamps=[],
        classe=None,
    )
    return breakdown["total"]


def score_breakdown(
    stamp_count: int,
    consents: dict,
    filieres,
    school_stamps: list = None,
    classe: str = None,
):
    """
    Lead scoring D1+D2+D3+D4 = 100pts max.
    D1 (25): intentionnalité déclarée — filières + profil
    D2 (40): comportement in-fair — nb stands visités (no diversity bonus)
    D3 (20): pertinence — % stands cohérents avec filières déclarées
    D4 (15): valeur commerciale — consentements
    Hard rule: stamp_count == 0 → total = 0. Capped at 98.
    """
    fil = list(filieres or [])
    cons = consents or {}
    stamps = school_stamps or []

    # D1 - Intentionnalité déclarée (25 pts max)
    n_fil = len(fil)
    d1_filieres = {0: 0, 1: 8, 2: 16}.get(n_fil, 22)
    d1_classe = 3 if classe and any(k in classe for k in ("Terminale", "Étudiant")) else 0
    d1_total = min(25, d1_filieres + d1_classe)

    # D2 - Comportement in-fair (40 pts max) — no diversity bonus
    d2_total = min(stamp_count, 10) * 4

    # D3 - Pertinence des visites (20 pts max)
    if stamps and fil:
        user_halls = {FILIERE_TO_HALL[f] for f in fil if f in FILIERE_TO_HALL}
        relevant = sum(1 for st in stamps if st.get("hall_id") in user_halls)
        pct = relevant / len(stamps)
        if pct >= 0.70:
            d3_total = 20
        elif pct >= 0.50:
            d3_total = 14
        elif pct >= 0.30:
            d3_total = 8
        else:
            d3_total = 0
    else:
        d3_total = 0

    # D4 - Valeur commerciale (15 pts max)
    d4_diplomeo = 6 if cons.get("d") else 0
    d4_partenaires = 4 if cons.get("c") else 0
    d4_letudiant = 3 if cons.get("l") else 0
    d4_enquetes = 2 if cons.get("e") else 0
    d4_total = d4_diplomeo + d4_partenaires + d4_letudiant + d4_enquetes

    raw = d1_total + d2_total + d3_total + d4_total
    capped = 0 if stamp_count == 0 else min(98, round(raw))

    return {
        "total": int(capped),
        "raw": round(raw, 1),
        "gating_zero": stamp_count == 0,
        "dimensions": [
            {
                "key": "D1",
                "label": "Intentionnalité déclarée",
                "weight": "25%",
                "value": round(d1_total, 1),
                "max": 25,
                "items": [
                    {"label": f"{n_fil} filière(s) → {d1_filieres}pts", "pts": d1_filieres, "max": 22},
                    {"label": "Profil Terminale/Étudiant", "pts": d1_classe, "max": 3},
                ],
            },
            {
                "key": "D2",
                "label": "Comportement in-fair",
                "weight": "40%",
                "value": round(d2_total, 1),
                "max": 40,
                "critical": True,
                "items": [
                    {"label": f"{min(stamp_count, 10)} stand(s) × 4", "pts": d2_total, "max": 40},
                ],
            },
            {
                "key": "D3",
                "label": "Pertinence des visites",
                "weight": "20%",
                "value": round(d3_total, 1),
                "max": 20,
                "items": [
                    {"label": "% stands dans filières déclarées", "pts": d3_total, "max": 20},
                ],
            },
            {
                "key": "D4",
                "label": "Valeur commerciale",
                "weight": "15%",
                "value": round(d4_total, 1),
                "max": 15,
                "items": [
                    {"label": "Diplomeo", "pts": d4_diplomeo, "max": 6},
                    {"label": "Partenaires", "pts": d4_partenaires, "max": 4},
                    {"label": "L'Étudiant", "pts": d4_letudiant, "max": 3},
                    {"label": "Enquêtes", "pts": d4_enquetes, "max": 2},
                ],
            },
        ],
    }


def lead_temperature(score: int):
    if score >= 76:
        return {"label": "🔥 Hot", "color": "#dc2626", "value": "hot"}
    if score >= 55:
        return {"label": "♨️ Tiède", "color": "#f59e0b", "value": "warm"}
    if score >= 30:
        return {"label": "❄️ Froid", "color": "#3b82f6", "value": "cold"}
    return {"label": "🚫 Non-qualifié", "color": "#9ca3af", "value": "none"}


def lead_value_eur(score: int):
    """Diplomeo lead value range 40-80€ — applied progressively above 55."""
    if score >= 76:
        return 80
    if score >= 55:
        return 40 + round((score - 55) * 40 / 21)
    return 0  # below threshold = not transmissible


# ============== BADGES ==============
BADGES_DEFS = [
    {"id": "first", "label": "Premier pas", "icon": "👣", "desc": "Ton 1er tampon"},
    {"id": "explorer", "label": "Explorer", "icon": "🧭", "desc": "1 stand par pôle"},
    {"id": "marathon", "label": "Marathonien", "icon": "🏃", "desc": "5+ stands visités"},
    {"id": "curieux", "label": "Curieux", "icon": "🎤", "desc": "1 conférence suivie"},
    {"id": "premium", "label": "Premium", "icon": "💎", "desc": "Stand d'une filière premium"},
    {"id": "completiste", "label": "Complétiste", "icon": "🏆", "desc": "10+ stands"},
]


def compute_badges(stamps, schools_by_id, conf_count: int, filieres):
    """Return list of badge ids unlocked."""
    unlocked = set()
    if len(stamps) >= 1:
        unlocked.add("first")
    if len(stamps) >= 5:
        unlocked.add("marathon")
    if len(stamps) >= 10:
        unlocked.add("completiste")
    if conf_count >= 1:
        unlocked.add("curieux")
    # Explorer: at least 1 stamp in each non-conference hall
    halls_visited = set()
    for st in stamps:
        sc = schools_by_id.get(st.get("school_id"))
        if sc and sc.get("hall_id") and sc["hall_id"] != "k":
            halls_visited.add(sc["hall_id"])
    non_conf_halls = {h["id"] for h in HALLS_SEED if h["id"] != "k"}
    if non_conf_halls.issubset(halls_visited):
        unlocked.add("explorer")
    # Premium: visited at least one stamp in a hall matching their premium filière
    premium_hall_map = {"Ingénierie": "i", "Numérique": "i", "Commerce": "c", "Sciences Po": "s"}
    user_premium_halls = {premium_hall_map[f] for f in (filieres or []) if f in premium_hall_map}
    if any(
        (schools_by_id.get(st.get("school_id")) or {}).get("hall_id") in user_premium_halls
        for st in stamps
    ):
        unlocked.add("premium")
    return [b for b in BADGES_DEFS if b["id"] in unlocked]


# ============== ROUTES ==============
@api_router.get("/")
async def root():
    return {"app": "PasseportEtudiant", "version": "1.0"}


@api_router.get("/halls")
async def get_halls():
    return HALLS_SEED


@api_router.get("/schools")
async def get_schools():
    schools = await db.schools.find({}, {"_id": 0}).to_list(500)
    return schools


@api_router.get("/schools/{school_id}")
async def get_school(school_id: str):
    s = await db.schools.find_one({"id": school_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "School not found")
    return s


# ------- Classes -------
@api_router.post("/classes")
async def create_class(body: ClassCreate):
    code = "PROF" + secrets.token_hex(2).upper()
    while await db.classes.find_one({"code": code}):
        code = "PROF" + secrets.token_hex(2).upper()
    doc = {
        "id": str(uuid.uuid4()),
        "code": code,
        "teacher_name": body.teacher_name,
        "school_name": body.school_name,
        "created_at": now_iso(),
    }
    await db.classes.insert_one(dict(doc))
    return clean_doc(doc)


@api_router.get("/classes/{code}")
async def get_class(code: str):
    c = await db.classes.find_one({"code": code.upper()}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Class not found")
    return c


@api_router.get("/classes/{code}/students")
async def get_class_students(code: str):
    c = await db.classes.find_one({"code": code.upper()}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Class not found")
    students = await db.students.find({"class_code": code.upper()}, {"_id": 0}).to_list(500)
    # Attach stamp counts
    for s in students:
        count = await db.stamps.count_documents({"student_id": s["id"]})
        s["stamp_count"] = count
    return {"class": c, "students": students}


# ------- Students -------
@api_router.get("/students")
async def list_students(include_demo: bool = False, limit: int = 50):
    """List all students (excluding anonymous). Used to populate the Select page."""
    query = {"is_anonymous": {"$ne": True}}
    if not include_demo:
        query["is_demo"] = {"$ne": True}
    query["$or"] = [{"is_guest": {"$ne": True}}, {"guest_claimed": True}]
    students = (
        await db.students.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    for s in students:
        s["stamp_count"] = await db.stamps.count_documents({"student_id": s["id"]})
    return students


@api_router.post("/students")
async def create_student(body: StudentCreate):
    code = body.class_code.upper().strip() if body.class_code else None
    if code:
        c = await db.classes.find_one({"code": code})
        if not c:
            raise HTTPException(400, "Code professeur invalide")
    serial = f"SAL-2026-{secrets.randbelow(90000) + 10000}"
    student = Student(
        serial=serial,
        name=body.name,
        emoji=body.emoji,
        classe=body.classe,
        filieres=body.filieres,
        formation=body.formation,
        class_code=code,
    )
    doc = student.model_dump()
    await db.students.insert_one(dict(doc))
    return clean_doc(doc)


@api_router.post("/students/guest")
async def create_guest_student():
    serial = f"INV-2026-{secrets.randbelow(90000) + 10000}"
    student = Student(
        serial=serial,
        name="Invité salon",
        emoji="🎒",
        classe="Groupe professeur",
        filieres=[],
        formation=[],
        consents=Consents(l=False, d=False, c=False, e=False),
        is_guest=True,
        guest_claimed=False,
    )
    doc = student.model_dump()
    await db.students.insert_one(dict(doc))
    return clean_doc(doc)


@api_router.post("/students/{student_id}/claim")
async def claim_guest_student(student_id: str, body: GuestClaim):
    current = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "Student not found")
    if current.get("is_anonymous"):
        raise HTTPException(403, "Profil anonyme non convertible")

    first_name = body.first_name.strip()
    last_name = body.last_name.strip()
    email = body.email.strip().lower()
    if not first_name:
        raise HTTPException(400, "Prénom requis")
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Email invalide")

    update = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "name": f"{first_name} {last_name}".strip(),
        "is_guest": True,
        "guest_claimed": True,
        "claimed_at": now_iso(),
        "email_opened": True,
        "consents.l": True,
        "consents.e": True,
    }
    await db.students.update_one({"id": student_id}, {"$set": update})
    return await get_student(student_id)


@api_router.get("/students/{student_id}")
async def get_student(student_id: str):
    s = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Student not found")
    return s


@api_router.patch("/students/{student_id}")
async def update_student(student_id: str, body: StudentUpdate):
    current = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "Student not found")
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "consents" in update and update["consents"] is not None:
        update["consents"] = dict(update["consents"])
        # Audit trail: log every consent change
        old_c = current.get("consents") or {}
        new_c = update["consents"]
        for key in ("l", "d", "c", "e"):
            if old_c.get(key) != new_c.get(key):
                await db.consent_audit.insert_one({
                    "id": str(uuid.uuid4()),
                    "student_id": student_id,
                    "consent_key": key,
                    "from": bool(old_c.get(key)),
                    "to": bool(new_c.get(key)),
                    "timestamp": now_iso(),
                })
    if not update:
        return await get_student(student_id)
    await db.students.update_one({"id": student_id}, {"$set": update})
    return await get_student(student_id)


# ------- RGPD -------
@api_router.get("/students/{student_id}/rgpd")
async def rgpd_view(student_id: str):
    """Returns everything stored about a student + audit trail. Right to access."""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    stamps = await db.stamps.find({"student_id": student_id}, {"_id": 0}).to_list(500)
    audit = (
        await db.consent_audit.find({"student_id": student_id}, {"_id": 0})
        .sort("timestamp", -1)
        .to_list(500)
    )
    return {
        "student": student,
        "stamps": stamps,
        "consent_audit": audit,
        "rights": {
            "access": "Right to access your data — this endpoint",
            "portability": f"GET /api/students/{student_id}/rgpd?export=json",
            "rectification": f"PATCH /api/students/{student_id}",
            "erasure": f"DELETE /api/students/{student_id}",
        },
    }


@api_router.get("/students/{student_id}/rgpd/export")
async def rgpd_export(student_id: str):
    """Right to data portability — downloadable JSON."""
    data = await rgpd_view(student_id)
    payload = io.StringIO()
    import json as _json
    _json.dump(data, payload, ensure_ascii=False, indent=2, default=str)
    payload.seek(0)
    return StreamingResponse(
        iter([payload.getvalue()]),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="rgpd_export_{student_id}.json"'
        },
    )


@api_router.delete("/students/{student_id}")
async def delete_student(student_id: str):
    """Right to erasure (RGPD Art. 17). Demo profiles protected."""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    if student.get("is_demo"):
        raise HTTPException(403, "Demo profiles can't be deleted")
    await db.stamps.delete_many({"student_id": student_id})
    await db.consent_audit.delete_many({"student_id": student_id})
    await db.students.delete_one({"id": student_id})
    return {"ok": True}


# ------- Stamps -------
@api_router.get("/students/{student_id}/stamps")
async def list_stamps(student_id: str):
    stamps = await db.stamps.find({"student_id": student_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    return stamps


@api_router.post("/stamps")
async def create_stamp(body: StampCreate):
    student = await db.students.find_one({"id": body.student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    if student.get("is_anonymous"):
        raise HTTPException(403, "Profil anonyme — pas de tampon possible")
    school_lookup = qr_payload_to_school_lookup(body.qr_token)
    school = await db.schools.find_one({"qr_token": school_lookup}, {"_id": 0})
    if not school:
        # Allow direct school_id fallback
        school = await db.schools.find_one({"id": school_lookup}, {"_id": 0})
    if not school:
        raise HTTPException(400, "QR inconnu")

    existing = await db.stamps.find_one({"student_id": body.student_id, "school_id": school["id"]}, {"_id": 0})
    if existing:
        return {"stamp": existing, "duplicate": True, "school": school}

    now = datetime.now(timezone.utc)
    stamp = Stamp(
        student_id=body.student_id,
        school_id=school["id"],
        hall_id=school["hall_id"],
        school_name=school["name"],
        time_label=f"{now.hour}h{str(now.minute).zfill(2)}",
    )
    doc = stamp.model_dump()
    await db.stamps.insert_one(dict(doc))
    await db.students.update_one({"id": body.student_id}, {"$set": {"scan_exposant": True}})
    return {"stamp": clean_doc(doc), "duplicate": False, "school": school}


@api_router.delete("/stamps/{stamp_id}")
async def delete_stamp(stamp_id: str):
    res = await db.stamps.delete_one({"id": stamp_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Stamp not found")
    return {"ok": True}


@api_router.patch("/stamps/{stamp_id}/rating")
async def rate_stamp(stamp_id: str, body: StampRating):
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "Rating must be between 1 and 5")
    res = await db.stamps.update_one({"id": stamp_id}, {"$set": {"rating": body.rating}})
    if res.matched_count == 0:
        raise HTTPException(404, "Stamp not found")
    stamp = await db.stamps.find_one({"id": stamp_id}, {"_id": 0})
    return clean_doc(stamp)


# ------- Recap -------
@api_router.get("/students/{student_id}/recap")
async def recap(student_id: str):
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    stamps = await db.stamps.find({"student_id": student_id}, {"_id": 0}).to_list(500)
    consents = student.get("consents", {})
    filieres = student.get("filieres", [])

    # Split stamps: schools vs conferences (hall_id == "k")
    school_stamps = [s for s in stamps if s.get("hall_id") != "k"]
    conf_stamps = [s for s in stamps if s.get("hall_id") == "k"]

    breakdown = score_breakdown(
        stamp_count=len(school_stamps),
        consents=consents,
        filieres=filieres,
        school_stamps=school_stamps,
        classe=student.get("classe"),
    )
    score = breakdown["total"]

    # Recos
    schools = await db.schools.find({}, {"_id": 0}).to_list(500)
    schools_by_id = {sc["id"]: sc for sc in schools}
    visited_ids = {s["school_id"] for s in stamps}

    # Score each visited school: filière match + star rating + consents → top 5
    recos = []
    if not student.get("is_anonymous"):
        for st in school_stamps:
            sc = schools_by_id.get(st["school_id"])
            if not sc:
                continue
            score_match = 0
            why = []

            # 0-50pts: filière-type keyword match
            fil_pts = _filiere_type_score(filieres, sc["type"])
            if fil_pts > 0:
                score_match += fil_pts
                why.append(f"+{fil_pts} correspondance filière")

            # 0-40pts: student's own star rating
            if st.get("rating"):
                rating_pts = st["rating"] * 8
                score_match += rating_pts
                why.append(f"+{rating_pts} ta note ({st['rating']}⭐)")

            # 0-10pts: consentements lead
            if consents.get("d") or consents.get("c"):
                score_match += 10
                why.append("+10 lead qualifié")

            recos.append({
                "name": sc["name"],
                "type": sc["type"],
                "school_id": sc["id"],
                "m": min(98, score_match),
                "t": score_match >= 70,
                "why": why,
            })
        recos.sort(key=lambda r: -r["m"])
        recos = recos[:5]

    # Next steps
    next_steps = []
    if not student.get("is_anonymous"):
        if filieres and "Ingénierie" in filieres:
            next_steps.append({"t": "JPO CentraleSupélec", "d": "14 mai 2026", "c": "#E3000B"})
        if filieres and "Commerce" in filieres:
            next_steps.append({"t": "JPO HEC Paris", "d": "20 mai 2026", "c": "#E3000B"})
        next_steps.append({"t": "Clôture vœux Parcoursup", "d": "10 mai 2026", "c": "#1A237E"})
        next_steps.append({"t": "Webinaire Orientation", "d": "8 mai 2026", "c": "#6D28D9"})

    badges = compute_badges(stamps, schools_by_id, len(conf_stamps), filieres)

    return {
        "student": student,
        "stamps": stamps,
        "school_stamps_count": len(school_stamps),
        "conf_stamps_count": len(conf_stamps),
        "score": score,
        "score_breakdown": breakdown,
        "temperature": lead_temperature(score),
        "lead_value_eur": lead_value_eur(score),
        "recos": recos,
        "next": next_steps,
        "badges": badges,
        "all_badges": BADGES_DEFS,
        "duration_min": 30 + len(stamps) * 8 if len(stamps) > 0 else 0,
    }


# ------- Analytics -------
@api_router.get("/analytics/overview")
async def analytics_overview():
    total_students = await db.students.count_documents({"is_anonymous": {"$ne": True}})
    total_stamps = await db.stamps.count_documents({})
    total_classes = await db.classes.count_documents({})

    # Top schools
    pipeline = [
        {"$group": {"_id": "$school_id", "count": {"$sum": 1}, "name": {"$first": "$school_name"}, "hall_id": {"$first": "$hall_id"}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_schools = []
    async for row in db.stamps.aggregate(pipeline):
        top_schools.append({"school_id": row["_id"], "name": row["name"], "hall_id": row["hall_id"], "count": row["count"]})

    # Stamps per hall
    hall_pipeline = [
        {"$group": {"_id": "$hall_id", "count": {"$sum": 1}}},
    ]
    hall_counts_raw = []
    async for row in db.stamps.aggregate(hall_pipeline):
        hall_counts_raw.append({"hall_id": row["_id"], "count": row["count"]})
    hall_counts = [
        {
            "hall_id": h["id"],
            "label": h["label"],
            "color": h["color"],
            "count": next((x["count"] for x in hall_counts_raw if x["hall_id"] == h["id"]), 0),
        }
        for h in HALLS_SEED
    ]

    # Consents aggregate
    consent_pipeline = [
        {"$match": {"is_anonymous": {"$ne": True}}},
        {"$group": {
            "_id": None,
            "l": {"$sum": {"$cond": ["$consents.l", 1, 0]}},
            "d": {"$sum": {"$cond": ["$consents.d", 1, 0]}},
            "c": {"$sum": {"$cond": ["$consents.c", 1, 0]}},
            "e": {"$sum": {"$cond": ["$consents.e", 1, 0]}},
        }},
    ]
    consents = {"l": 0, "d": 0, "c": 0, "e": 0}
    async for row in db.students.aggregate(consent_pipeline):
        consents = {"l": row["l"], "d": row["d"], "c": row["c"], "e": row["e"]}

    # Filières distribution
    fil_pipeline = [
        {"$match": {"is_anonymous": {"$ne": True}}},
        {"$unwind": "$filieres"},
        {"$group": {"_id": "$filieres", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    filieres_dist = []
    async for row in db.students.aggregate(fil_pipeline):
        filieres_dist.append({"filiere": row["_id"], "count": row["count"]})

    # Recent activity
    recent = await db.stamps.find({}, {"_id": 0}).sort("timestamp", -1).limit(10).to_list(10)

    # Demo QR board status: per-booth status for the presentation QR codes.
    demo_booths = []
    for booth in DEMO_QR_BOOTHS:
        school = await db.schools.find_one({"id": booth["school_id"]}, {"_id": 0})
        demo_stamp = await db.stamps.find_one(
            {"student_id": DEMO_QR_STUDENT_ID, "school_id": booth["school_id"]},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        total_visits = await db.stamps.count_documents({"school_id": booth["school_id"]})
        demo_booths.append({
            "school_id": booth["school_id"],
            "label": booth["label"],
            "name": school["name"] if school else booth["school_id"],
            "visited": demo_stamp is not None,
            "time_label": demo_stamp.get("time_label") if demo_stamp else None,
            "timestamp": demo_stamp.get("timestamp") if demo_stamp else None,
            "total_visits": total_visits,
        })

    return {
        "total_students": total_students,
        "total_stamps": total_stamps,
        "total_classes": total_classes,
        "avg_stamps": round(total_stamps / total_students, 1) if total_students > 0 else 0,
        "top_schools": top_schools,
        "hall_counts": hall_counts,
        "consents": consents,
        "filieres_dist": filieres_dist,
        "recent": recent,
        "demo_booths": demo_booths,
    }


@api_router.delete("/classes/{code}")
async def delete_class(code: str, cascade: bool = False):
    """Delete a class. If cascade=true, also deletes its students and stamps.
    Demo classes PROF2026 and PROF2026B are protected."""
    code_u = code.upper()
    if code_u in ("PROF2026", "PROF2026B"):
        raise HTTPException(403, f"Demo class {code_u} is protected")
    c = await db.classes.find_one({"code": code_u})
    if not c:
        raise HTTPException(404, "Class not found")
    deleted_students = 0
    deleted_stamps = 0
    if cascade:
        student_ids = [
            s["id"]
            async for s in db.students.find({"class_code": code_u}, {"id": 1, "_id": 0})
        ]
        if student_ids:
            sres = await db.stamps.delete_many({"student_id": {"$in": student_ids}})
            deleted_stamps = sres.deleted_count
            stres = await db.students.delete_many({"class_code": code_u})
            deleted_students = stres.deleted_count
    await db.classes.delete_one({"code": code_u})
    return {
        "ok": True,
        "deleted_class": code_u,
        "deleted_students": deleted_students,
        "deleted_stamps": deleted_stamps,
    }


@api_router.post("/admin/reset")
async def admin_reset(keep_demo: bool = True):
    """DANGER: Wipe all non-demo data. Keeps demo students and PROF2026/PROF2026B by default."""
    student_filter = {"is_demo": {"$ne": True}} if keep_demo else {}
    students_deleted = await db.students.delete_many(student_filter)
    if keep_demo:
        # Keep stamps for all demo students
        demo_student_ids = ["demo-lucas", "demo-theo", "demo-emma", "demo-nadia", "demo-hugo", "demo-sarah", "demo-malik", "demo-lea"]
        stamps_deleted = await db.stamps.delete_many(
            {"student_id": {"$nin": demo_student_ids}}
        )
        classes_deleted = await db.classes.delete_many({"code": {"$nin": ["PROF2026", "PROF2026B"]}})
    else:
        stamps_deleted = await db.stamps.delete_many({})
        classes_deleted = await db.classes.delete_many({})
    return {
        "ok": True,
        "keep_demo": keep_demo,
        "students_deleted": students_deleted.deleted_count,
        "stamps_deleted": stamps_deleted.deleted_count,
        "classes_deleted": classes_deleted.deleted_count,
    }


# Include the router in the main app


# ------- Leaderboard -------
@api_router.get("/leaderboard")
async def classes_leaderboard():
    """Ranked list of classes by avg stamps/student. Returns up to 20."""
    classes = await db.classes.find({}, {"_id": 0}).to_list(200)
    rows = []
    for c in classes:
        students = await db.students.find(
            {"class_code": c["code"], "is_anonymous": {"$ne": True}},
            {"id": 1, "_id": 0},
        ).to_list(500)
        total_stamps = 0
        for s in students:
            total_stamps += await db.stamps.count_documents({"student_id": s["id"]})
        n = len(students)
        rows.append({
            "code": c["code"],
            "school_name": c["school_name"],
            "teacher_name": c["teacher_name"],
            "students": n,
            "stamps": total_stamps,
            "avg": round(total_stamps / n, 2) if n else 0.0,
        })
    rows.sort(key=lambda r: (-r["avg"], -r["stamps"], -r["students"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows[:20]


# ------- Leads qualifiés -------
def _passes_lead_filter(student, filiere, consent, min_stamps, stamp_count):
    if filiere and filiere != "all":
        if filiere not in (student.get("filieres") or []):
            return False
    if consent and consent != "all":
        if not student.get("consents", {}).get(consent):
            return False
    if stamp_count < min_stamps:
        return False
    return True


@api_router.get("/analytics/leads")
async def leads(
    filiere: Optional[str] = "all",
    consent: Optional[str] = "all",
    min_stamps: int = 0,
    limit: int = 200,
):
    students = await db.students.find(
        {
            "is_anonymous": {"$ne": True},
            "$or": [{"is_guest": {"$ne": True}}, {"guest_claimed": True}],
        },
        {"_id": 0},
    ).sort("created_at", -1).to_list(1000)
    rows = []
    for s in students:
        stamp_count = await db.stamps.count_documents({"student_id": s["id"]})
        if not _passes_lead_filter(s, filiere, consent, min_stamps, stamp_count):
            continue
        consents = s.get("consents") or {}
        school_stamps_list = await db.stamps.find(
            {"student_id": s["id"], "hall_id": {"$ne": "k"}},
            {"hall_id": 1, "_id": 0},
        ).to_list(500)
        breakdown = score_breakdown(
            stamp_count=len(school_stamps_list),
            consents=consents,
            filieres=s.get("filieres") or [],
            school_stamps=school_stamps_list,
            classe=s.get("classe"),
        )
        score = breakdown["total"]
        rows.append({
            "id": s["id"],
            "name": s["name"],
            "email": s.get("email"),
            "serial": s["serial"],
            "classe": s["classe"],
            "filieres": s.get("filieres") or [],
            "formation": s.get("formation") or [],
            "class_code": s.get("class_code"),
            "consents": consents,
            "stamp_count": stamp_count,
            "score": score,
            "score_breakdown": breakdown,
            "temperature": lead_temperature(score),
            "lead_value_eur": lead_value_eur(score),
            "is_demo": s.get("is_demo", False),
            "is_guest": s.get("is_guest", False),
            "guest_claimed": s.get("guest_claimed", False),
        })
    rows.sort(key=lambda r: (-r["score"], -r["stamp_count"]))
    return rows[:limit]


@api_router.get("/analytics/leads.csv")
async def leads_csv(
    filiere: Optional[str] = "all",
    consent: Optional[str] = "all",
    min_stamps: int = 0,
):
    rows = await leads(filiere=filiere, consent=consent, min_stamps=min_stamps, limit=10000)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Nom", "Serial", "Classe", "Filières", "Formation", "Code classe",
        "Tampons", "Score",
        "Consent_lEtudiant", "Consent_Diplomeo", "Consent_Partenaires", "Consent_Enquetes",
    ])
    for r in rows:
        c = r.get("consents") or {}
        writer.writerow([
            r["name"], r["serial"], r["classe"],
            ", ".join(r["filieres"]),
            ", ".join(r["formation"]),
            r.get("class_code") or "",
            r["stamp_count"], r["score"],
            "oui" if c.get("l") else "non",
            "oui" if c.get("d") else "non",
            "oui" if c.get("c") else "non",
            "oui" if c.get("e") else "non",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="leads_passeport_etudiant.csv"'
        },
    )


# ------- Admin -------
@api_router.get("/admin/stats")
async def admin_stats():
    return {
        "students": {
            "total": await db.students.count_documents({}),
            "real": await db.students.count_documents(
                {"is_demo": {"$ne": True}, "is_anonymous": {"$ne": True}}
            ),
            "demo": await db.students.count_documents({"is_demo": True}),
            "anonymous": await db.students.count_documents({"is_anonymous": True}),
        },
        "stamps": await db.stamps.count_documents({}),
        "classes": await db.classes.count_documents({}),
        "schools": await db.schools.count_documents({}),
    }


@api_router.get("/admin/all-students")
async def admin_all_students():
    students = await db.students.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for s in students:
        s["stamp_count"] = await db.stamps.count_documents({"student_id": s["id"]})
    return students


@api_router.get("/admin/all-classes")
async def admin_all_classes():
    classes = await db.classes.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for c in classes:
        c["student_count"] = await db.students.count_documents({"class_code": c["code"]})
    return classes



app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    await seed_database()
    logger.info("Seed done.")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
