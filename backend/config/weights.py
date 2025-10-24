all_weights = ["kda", "cs", "gold", "damage_dealt", "vision_score",
               "cc_score", "healing_done", "shield_amount", "damage_taken"]

activate_weights = {

    # Rôle polyvalent, la liste est parfaite.
    "TOP": ["kda", "cs", "gold", "damage_dealt", "vision_score", "cc_score", "damage_taken"],

    # Très solide, le jungler doit aussi pouvoir tanker et contrôler la carte.
    "JUNGLE": ["kda", "cs", "gold", "damage_dealt", "vision_score", "cc_score", "damage_taken"],

    # Axé sur les dégâts et le contrôle. "damage_taken" est moins pertinent pour ce rôle.
    "MIDDLE": ["kda", "cs", "gold", "damage_dealt", "vision_score", "cc_score"],

    # Le carry pur. "damage_taken" n'est pas son rôle et est retiré.
    # "damage_dealt" devient la stat la plus importante ici.
    "BOTTOM": ["kda", "cs", "gold", "damage_dealt", "vision_score"],

    # Le protecteur. Ajout de "damage_taken" pour valoriser les supports tanks (Leona, Braum).
    "UTILITY": ["kda", "vision_score", "cc_score", "healing_done", "shield_amount", "damage_taken"]
}
