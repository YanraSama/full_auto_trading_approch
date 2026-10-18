import os
import warnings
import joblib
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_CANDIDATES = [
    "day_of_week", "hour", "minutes", "trend", "rr", "side",
    "anticipation", "chart_patern", "strat_trend", "patern_candle",
    "analyse_area", "hedge_strat", "sma_50", "sma_200", "bollinger",
    "atr", "rsi",
]
THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]


def build_models():
    return {
        "random_forest": Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
            ("model", RandomForestClassifier(
                n_estimators=500, max_depth=10, min_samples_leaf=5,
                class_weight="balanced", random_state=42, n_jobs=-1
            )),
        ]),
        "logistic_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(
                class_weight="balanced", max_iter=3000,
                solver="lbfgs", random_state=42
            )),
        ]),
    }


def feature_importance(fitted_pipeline, feature_cols, model_name):
    estimator = fitted_pipeline.named_steps["model"]
    if model_name == "random_forest":
        values = estimator.feature_importances_
        result = pd.Series(values, index=feature_cols, name="importance")
        return result.sort_values(ascending=False)
    values = estimator.coef_[0]
    result = pd.Series(values, index=feature_cols, name="coefficient")
    return result.reindex(result.abs().sort_values(ascending=False).index)


def evaluate_thresholds(y_true, probabilities):
    y_array = np.asarray(y_true)
    print("\n=== PERFORMANCE PAR SEUIL — dernier fold ===")
    for threshold in THRESHOLDS:
        mask = probabilities >= threshold
        n = int(mask.sum())
        if n == 0:
            print(f"Seuil {threshold:.2f} | aucun signal positif")
            continue
        wr = y_array[mask].mean() * 100
        coverage = n / len(probabilities) * 100
        acc = accuracy_score(y_array, mask.astype(int))
        tp = int((mask & (y_array == 1)).sum())
        fp = int((mask & (y_array == 0)).sum())
        print(f"Seuil {threshold:.2f} | N={n:6d} ({coverage:4.1f}%) | "
              f"WR={wr:5.1f}% | TP={tp:5d} | FP={fp:5d} | Acc={acc:.3f}")


def train_and_evaluate(model_name, template, X, y, feature_cols, output_path):
    print("\n" + "=" * 68 + f"\nMODÈLE : {model_name.upper()}\n" + "=" * 68)
    tscv = TimeSeriesSplit(n_splits=5)
    auc_scores = []
    last_y_test = last_proba = None

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), start=1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        if y_train.nunique() < 2 or y_test.nunique() < 2:
            warnings.warn(f"Fold {fold} ignoré : une classe manque dans train ou test.")
            continue
        model = clone(template)
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, proba)
        auc_scores.append(auc)
        print(f"Fold {fold} | Train={len(train_idx)} | Test={len(test_idx)} | AUC={auc:.4f}")
        last_y_test, last_proba = y_test, proba

    if not auc_scores or last_y_test is None:
        raise ValueError("AUC impossible à calculer : vérifie les classes de target et la taille du CSV.")

    print(f"\nAUC moyen : {np.mean(auc_scores):.4f} (± {np.std(auc_scores):.4f})")
    evaluate_thresholds(last_y_test, last_proba)

    threshold = 0.50
    predictions = (last_proba >= threshold).astype(int)
    print(f"\n=== RÉSULTATS DU DERNIER FOLD (seuil={threshold:.2f}) ===")
    print(f"Accuracy : {accuracy_score(last_y_test, predictions):.4f}")
    print(f"AUC      : {roc_auc_score(last_y_test, last_proba):.4f}")
    print(classification_report(last_y_test, predictions, zero_division=0))
    print("Matrice de confusion :\n", confusion_matrix(last_y_test, predictions))

    # Le modèle sauvegardé est réentraîné sur toutes les données après l'évaluation chronologique.
    final_model = clone(template)
    final_model.fit(X, y)
    importance = feature_importance(final_model, feature_cols, model_name)
    print("\nVariables influentes / coefficients :\n", importance.head(15))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    features_path = output_path.replace(".pkl", "_features.pkl")
    joblib.dump(final_model, output_path)
    joblib.dump(feature_cols, features_path)
    print(f"Modèle sauvegardé : {output_path}")
    print(f"Features sauvegardées : {features_path}")

    return {
        "mean_auc": float(np.mean(auc_scores)),
        "std_auc": float(np.std(auc_scores)),
        "last_fold_auc": float(roc_auc_score(last_y_test, last_proba)),
        "last_fold_accuracy": float(accuracy_score(last_y_test, predictions)),
        "confusion_matrix": confusion_matrix(last_y_test, predictions),
        "feature_importance": importance,
    }


def learning_data_classifier(csv_file="datas_models.csv"):
    df = pd.read_csv(csv_file, sep=";", encoding="utf-8-sig", low_memory=False)
    print(f"Nombre de lignes chargées : {len(df)}")
    if "target" not in df.columns:
        raise ValueError("Le CSV doit contenir une colonne 'target'.")

    df["target"] = pd.to_numeric(df["target"], errors="coerce")
    df = df.dropna(subset=["target"]).copy()
    if not set(df["target"].unique()).issubset({0, 1, 0.0, 1.0}):
        raise ValueError("La colonne target doit contenir uniquement 0 et 1.")
    df["target"] = df["target"].astype(int)
    if df["target"].nunique() < 2:
        raise ValueError("target doit contenir des exemples de classe 0 et de classe 1.")
    print("Distribution target :\n", df["target"].value_counts().sort_index())

    feature_cols = [c for c in FEATURE_CANDIDATES if c in df.columns]
    missing = [c for c in FEATURE_CANDIDATES if c not in df.columns]
    if missing:
        print("Features absentes (ignorées) :", missing)
    if not feature_cols:
        raise ValueError("Aucune feature attendue n'est présente dans le CSV.")

    X = df[feature_cols].copy()
    for col in feature_cols:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X = X.reset_index(drop=True)
    y = df["target"].reset_index(drop=True)
    print(f"Features utilisées ({len(feature_cols)}) : {feature_cols}")

    results = {}
    for name, model in build_models().items():
        filename = f"{name}_model_v3_target.pkl"
        results[name] = train_and_evaluate(name, model, X, y, feature_cols, filename)

    print("\n=== COMPARAISON DES MODÈLES ===")
    for name, result in results.items():
        print(f"{name:22s} | AUC moyen={result['mean_auc']:.4f} ± {result['std_auc']:.4f} "
              f"| AUC dernier fold={result['last_fold_auc']:.4f} "
              f"| Accuracy dernier fold={result['last_fold_accuracy']:.4f}")
    print("\nLes métriques sont calculées sur le dernier fold chronologique. "
          "Les fichiers sauvegardés sont ensuite réentraînés sur toutes les lignes.")
    return results


if __name__ == "__main__":
    learning_data_classifier("datas_models.csv")
