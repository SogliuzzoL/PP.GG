import pandas as pd


def select_features_intelligently(correlation_matrix, win_threshold, internal_threshold):
    """
    Algorithme de sélection de features basé sur la corrélation.
    Ne sélectionne que les corrélations POSITIVES avec 'win'.
    """
    try:
        correlations_with_win = correlation_matrix['win'].drop('win').abs()
    except KeyError:
        print("Erreur : La colonne 'win' est absente de la matrice de corrélation.")
        return []

    candidates = correlations_with_win[correlations_with_win >= win_threshold]
    sorted_candidates = candidates.sort_values(ascending=False)

    if sorted_candidates.empty:
        return []

    final_features = [sorted_candidates.index[0]]

    for new_feature in sorted_candidates.index[1:]:
        is_redundant = False
        for selected_feature in final_features:
            internal_correlation = correlation_matrix.loc[new_feature,
                                                          selected_feature]

            if abs(internal_correlation) > internal_threshold:
                is_redundant = True
                break

        if not is_redundant:
            final_features.append(new_feature)

    return final_features


def recommend_features(all_games_df, win_corr_threshold=0.25, internal_corr_threshold=0.75):
    """
    Analyse le DataFrame de toutes les parties et recommande les meilleures features par rôle.
    """
    roles = sorted(
        [role for role in all_games_df['role'].unique() if role != "UNKNOWN"])
    recommended_config = {}

    for role in roles:
        role_df = all_games_df[all_games_df['role'] == role]

        if len(role_df) < 1:
            continue

        numeric_role_df = role_df.select_dtypes(include=['number'])

        if 'win' not in numeric_role_df.columns:
            print(
                f"Avertissement : Colonne 'win' absente pour le rôle {role}, impossible de calculer la corrélation.")
            continue

        correlation_matrix = numeric_role_df.corr()

        selected_features = select_features_intelligently(
            correlation_matrix,
            win_corr_threshold,
            internal_corr_threshold
        )
        if selected_features:
            recommended_config[role] = selected_features

    return recommended_config
