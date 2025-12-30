import pandas as pd


def select_features_intelligently(correlation_matrix, win_threshold, internal_threshold):
    """
    Algorithme de sélection de features basé sur la corrélation.
    """
    try:
        if 'win' not in correlation_matrix.columns:
            return []

        # On prend la valeur absolue de la corrélation (les stats négatives comme 'deaths' comptent aussi)
        correlations_with_win = correlation_matrix['win'].drop(
            'win', errors='ignore').abs()
    except KeyError:
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


def recommend_features(all_games_df, win_corr_threshold=0.30, internal_corr_threshold=0.75):
    """
    Analyse le DataFrame de toutes les parties et recommande les meilleures features par rôle.
    """
    if all_games_df.empty:
        return {}

    roles = sorted(
        [r for r in all_games_df['role'].unique() if r and r != "UNKNOWN"])
    recommended_config = {}

    for role in roles:
        role_df = all_games_df[all_games_df['role'] == role]

        if len(role_df) < 5:
            continue

        # CORRECTION : On exclut explicitement les IDs du calcul de corrélation
        numeric_role_df = role_df.select_dtypes(include=['number'])
        cols_to_ignore = ['match_id', 'player_id', 'stat_id']
        numeric_role_df = numeric_role_df.drop(
            columns=[c for c in cols_to_ignore if c in numeric_role_df.columns])

        if 'win' not in numeric_role_df.columns:
            continue

        if numeric_role_df['win'].nunique() <= 1:
            continue

        correlation_matrix = numeric_role_df.corr()
        correlation_matrix = correlation_matrix.fillna(0)

        selected_features = select_features_intelligently(
            correlation_matrix,
            win_corr_threshold,
            internal_corr_threshold
        )

        if selected_features:
            recommended_config[role] = selected_features

    return recommended_config
