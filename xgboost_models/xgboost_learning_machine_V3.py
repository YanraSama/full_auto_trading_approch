import pandas as pd

import xgboost as xgb

from sklearn.model_selection import TimeSeriesSplit

from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, confusion_matrix, roc_curve

import joblib

import numpy as np

 

def learning_data_classifier(CSV_FILE, LEARNING_OUT):

 

    # ====================== CHARGEMENT ======================

    df = pd.read_csv(CSV_FILE, sep=";", encoding="utf-8-sig", low_memory=False)

    print(f"Nombre de trades : {len(df)}")

   

    # ── Supprimer les NaN du target ──

    df_train = df.dropna(subset=["target"]).reset_index(drop=True)

    df_train["target"] = df_train["target"].astype(int)  # 0 / 1 strict

 

    print(f"\nDataset d'entraînement : {len(df_train)} lignes")

    print("Distribution target :\n", df_train["target"].value_counts(normalize=True) * 100)

 

    feature_cols = [

        'day_of_week', 'hour', 'minutes', 'trend',

        'rr', 'side', 'anticipation', 'chart_patern', 'strat_trend',

        'patern_candle', 'analyse_area', 'hedge_strat', 'sma_50',

        'sma_200', 'alignement_tendances', 'bollinger', 'width_BB',

        'vol_rel', 'atr', 'rsi',

    ]

 

    feature_cols = [f for f in feature_cols if f in df_train.columns]

    print(f"\nFeatures utilisées ({len(feature_cols)}) : {feature_cols}")

 

    X = df_train[feature_cols].fillna(0)

    y = df_train["target"]

   

    # Extraction de la colonne 'rr' pour le calcul financier de l'espérance

    # Si le RR n'est pas fixe, on prend la valeur dynamique du trade, sinon on met 2.0 par défaut

    rr_values = df_train['rr'].fillna(2.0).values

 

    # ====================== VALIDATION CROISÉE CHRONOLOGIQUE ======================

    tscv = TimeSeriesSplit(n_splits=5)

    auc_scores = []

    best_thresholds_financial = []

   

    last_model = None

    last_y_test = None

    last_proba = None

    last_rr_test = None

 

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), start=1):

        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]

        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]      

        rr_test = rr_values[test_idx]

       

        ratio = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

 

        model = xgb.XGBClassifier(

            n_estimators          = 1000,

            learning_rate         = 0.03,

            max_depth             = 5,

            min_child_weight      = 5,

            subsample             = 0.75,

            colsample_bytree      = 0.70,

            colsample_bylevel     = 0.70,

            colsample_bynode      = 0.70,

            reg_alpha             = 0.5,

            reg_lambda            = 1.0,

            scale_pos_weight      = ratio,

            tree_method           = "hist",

            eval_metric           = "logloss",  

            early_stopping_rounds = 30,

            random_state          = 42,

            n_jobs                = -1,

        )

 

        model.fit(

            X_train, y_train,

            eval_set = [(X_test, y_test)],

            verbose  = False,

        )

 

        proba = model.predict_proba(X_test)[:, 1]

        auc   = roc_auc_score(y_test, proba)

        auc_scores.append(auc)

 

        # ── Détermination mathématique du seuil optimal par Profit sur ce Fold ──

        seuils_candidats = np.linspace(0.30, 0.75, 111)

        meilleur_profit_fold = -np.inf

        seuil_optimal_fold = 0.50

       

        for s in seuils_candidats:

            predictions = (proba >= s).astype(int)

            # Calcul du gain théorique : si gain (y=1) -> +RR, si perte (y=0) -> -1

            profit_th = np.sum(np.where(predictions == 1, np.where(y_test == 1, rr_test, -1.0), 0.0))

           

            if profit_th > meilleur_profit_fold:

                meilleur_profit_fold = profit_th

                seuil_optimal_fold = s

               

        best_thresholds_financial.append(seuil_optimal_fold)

        print(f"Fold {fold} AUC : {auc:.4f} | Seuil Opti Financier : {seuil_optimal_fold:.3f} (Profit: {meilleur_profit_fold:.1f}R)")

 

        last_model  = model

        last_y_test = y_test

        last_proba  = proba

        last_rr_test = rr_test

 

    # Synthèse mathématique globale

    seuil_moyen_financier = np.mean(best_thresholds_financial)

    print(f"\n=== AUC moyen : {np.mean(auc_scores):.4f} (± {np.std(auc_scores):.4f}) ===")

    print(f"=== SEUIL OPTIMAL MOYEN (Optimisation financière) : {seuil_moyen_financier:.3f} ===")

 

    # ── Option alternative statistique classique : Indice de Youden (Maximise Vrais Positifs - Faux Positifs) ──

    fpr, tpr, thresholds = roc_curve(last_y_test, last_proba)

    youden_idx = np.argmax(tpr - fpr)

    seuil_youden = thresholds[youden_idx]

    print(f"=== SEUIL OPTIMAL STATISTIQUE (Indice de Youden - Dernier fold) : {seuil_youden:.3f} ===")

 

    # ====================== RÉSULTATS FINAUX (Sur le seuil optimal financier) ======================

    seuil_final = seuil_moyen_financier

    pred_final  = (last_proba >= seuil_final).astype(int)

 

    print(f"\n=== RÉSULTATS SUR LE DERNIER FOLD AVEC LE SEUIL EN VALEUR RÉELLE ({seuil_final:.3f}) ===")

    print(f"Accuracy : {accuracy_score(last_y_test, pred_final):.4f}")

    print(f"AUC      : {roc_auc_score(last_y_test, last_proba):.4f}")

    print(classification_report(last_y_test, pred_final, zero_division=0))

    print("Matrice de confusion :\n", confusion_matrix(last_y_test, pred_final))

 

    # Profit total sur le dernier fold avec ce seuil automatique

    profit_final_dernier_fold = np.sum(np.where(pred_final == 1, np.where(last_y_test == 1, last_rr_test, -1.0), 0.0))

    print(f"Profit cumulé sur la période de test : {profit_final_dernier_fold:.1f} R (Unités de risque)")

 

    # ====================== FEATURE IMPORTANCE ======================

    importances = pd.Series(last_model.feature_importances_, index=feature_cols).sort_values(ascending=False)

    print("\nTop Features (Dernier Fold) :")

    print(importances.head(15))

 

    # ====================== SAUVEGARDE ======================

    # Sauvegarde du modèle et du seuil optimal trouvé dans un dictionnaire meta

    meta_package = {

        'model': last_model,

        'features': feature_cols,

        'optimal_threshold': seuil_final

    }

    joblib.dump(meta_package, LEARNING_OUT)

    print(f"\n✅ Package Modèle + Seuil automatique sauvegardé : {LEARNING_OUT}")

   

    return seuil_final

 
#learning_data_classifier("datas_models_1.csv", "xgboost_model_v3_package.pkl")