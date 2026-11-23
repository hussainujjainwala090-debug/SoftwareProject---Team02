"""Mapping from PlantVillage class names to AgriScan crops and disease names.

Only the classes for crops in the farm-profile list (UI-2) are used: tomato
and bell pepper. Disease names match the knowledge-base seed entries
(src/backend/app/seed_data.py) so a prediction links to a Diseases row.
PlantVillage has no date palm or cucumber; those need the team's own photos.
"""

# PlantVillage class name -> (crop, AgriScan label)
CLASS_MAP: dict[str, tuple[str, str]] = {
    "Tomato___Bacterial_spot": ("tomato", "Tomato bacterial spot"),
    "Tomato___Early_blight": ("tomato", "Tomato early blight"),
    "Tomato___Late_blight": ("tomato", "Tomato late blight"),
    "Tomato___Leaf_Mold": ("tomato", "Tomato leaf mold"),
    "Tomato___Septoria_leaf_spot": ("tomato", "Tomato Septoria leaf spot"),
    "Tomato___Spider_mites Two-spotted_spider_mite": ("tomato", "Tomato spider mites"),
    "Tomato___Target_Spot": ("tomato", "Tomato target spot"),
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": ("tomato", "Tomato yellow leaf curl virus"),
    "Tomato___Tomato_mosaic_virus": ("tomato", "Tomato mosaic virus"),
    "Tomato___healthy": ("tomato", "healthy"),
    "Pepper,_bell___Bacterial_spot": ("pepper", "Pepper bacterial spot"),
    "Pepper,_bell___healthy": ("pepper", "healthy"),
}
