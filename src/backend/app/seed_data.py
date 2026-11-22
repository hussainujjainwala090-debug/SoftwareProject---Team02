"""Starter knowledge-base entries for the prototype.

Names match the classifier labels (src/ml, PlantVillage tomato and pepper
classes) so a confident prediction can be linked to a Diseases row. Two date
palm entries are included for agronomist review, as the classifier has no date
palm training data yet.

The guidance is general and intentionally avoids product names and doses: it
must be checked by an agronomist before real use, and the admin can edit it
from the knowledge-base screen (UI-8).
"""
from app.schemas import DiseaseIn, TreatmentIn

PPE = "Wear gloves and a mask; follow the product label and the pre-harvest interval."
LABEL_ONLY = "Use only products registered for this crop in the UAE and follow the label dose."


def _t(kind: str, guidance: str, warning: str) -> TreatmentIn:
    return TreatmentIn(type=kind, guidance=guidance, safety_warning=warning)


def _fungal(name: str, crop: str, symptoms: str) -> DiseaseIn:
    return DiseaseIn(name=name, crop_type=crop, symptoms=symptoms, treatments=[
        _t("organic", "Remove and bag infected leaves; a neem oil or bicarbonate spray every 7 days can slow spread.", PPE),
        _t("chemical", "Apply a fungicide registered for this disease on this crop, rotating active ingredients.", LABEL_ONLY),
        _t("preventive", "Water at the base in the morning, space plants for airflow and avoid working with wet plants.",
           "Disinfect tools between plants."),
    ])


def _bacterial(name: str, crop: str, symptoms: str) -> DiseaseIn:
    return DiseaseIn(name=name, crop_type=crop, symptoms=symptoms, treatments=[
        _t("organic", "Remove infected leaves and avoid overhead watering; copper-based organic sprays can reduce spread.", PPE),
        _t("chemical", "Apply a copper-based bactericide registered for this crop.", LABEL_ONLY),
        _t("preventive", "Use certified clean seed or seedlings and rotate crops for at least two seasons.",
           "Disinfect tools between plants."),
    ])


def _viral(name: str, crop: str, symptoms: str, vector: str) -> DiseaseIn:
    return DiseaseIn(name=name, crop_type=crop, symptoms=symptoms, treatments=[
        _t("organic", "There is no cure: remove and destroy infected plants to protect healthy ones.",
           "Do not compost infected plants."),
        _t("chemical", f"No chemical cures the virus; control the {vector} with a registered product if needed.", LABEL_ONLY),
        _t("preventive", f"Use resistant varieties, control {vector} and keep weeds down around the crop.",
           "Wash hands and tools after handling infected plants."),
    ])


SEED_DISEASES: list[DiseaseIn] = [
    _bacterial("Tomato bacterial spot", "tomato", "Small dark, water-soaked spots on leaves and fruit."),
    _fungal("Tomato early blight", "tomato", "Brown spots with rings (target pattern) on older leaves."),
    _fungal("Tomato late blight", "tomato", "Large grey-green to brown patches; white mould under leaves in humid weather."),
    _fungal("Tomato leaf mold", "tomato", "Yellow patches on top of leaves, olive-green mould underneath."),
    _fungal("Tomato Septoria leaf spot", "tomato", "Many small round spots with dark edges and grey centres."),
    _fungal("Tomato target spot", "tomato", "Brown spots with light centres and rings on leaves."),
    DiseaseIn(name="Tomato spider mites", crop_type="tomato",
              symptoms="Fine yellow speckling on leaves, fine webbing underneath.", treatments=[
        _t("organic", "Spray the underside of leaves with water or insecticidal soap every 5-7 days.", PPE),
        _t("chemical", "Apply a miticide registered for tomato, rotating active ingredients.", LABEL_ONLY),
        _t("preventive", "Avoid drought stress and dust; check the underside of leaves weekly.",
           "Keep children and animals away from treated plants until dry."),
    ]),
    _viral("Tomato yellow leaf curl virus", "tomato", "Upward curling, yellow leaf edges, stunted plants.", "whiteflies"),
    _viral("Tomato mosaic virus", "tomato", "Light and dark green mosaic pattern, distorted leaves.", "spread by hands and tools"),
    _bacterial("Pepper bacterial spot", "pepper", "Small water-soaked spots turning brown on leaves."),
    _fungal("Date palm Graphiola leaf spot", "date_palm", "Small yellow-brown spots with black, powdery bumps on fronds."),
    _fungal("Date palm black scorch", "date_palm", "Black, burnt-looking lesions on fronds, buds and leaf bases."),
]
