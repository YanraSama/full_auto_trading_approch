"""
pipeline_mt4_xgboost.py
=======================
Orchestrateur : optimisation MT4 -> logs de signaux -> XGBoost -> validation -> déploiement.

Les fonctions marquées [STUB] sont les seules qui touchent MT4 : à brancher sur les
fonctions existantes de MT4.py (open_MT4, create_new_set, modify_text_file...).
Tout le reste (dataset, walk-forward, choix de config, portes de validation, boucle
multi-actifs) est du Python pur.

Colonnes attendues dans le CSV de signaux loggé par l'EA (séparateur ';') :
    time        date/heure d'ouverture du signal (ex. 2026.03.14 10:15)
    symbol, side
    <FEATURES>  les colonnes listées dans FEATURES ci-dessous
    resultat    profit net du trade (devise du compte), commission et swap inclus
"""
import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from dateutil.relativedelta import relativedelta
from sklearn.metrics import roc_auc_score

# ───────────────────────────── Configuration ─────────────────────────────
WORK_DIR = Path("pipeline_runs")
ACTIFS = ["US500.cash", "UKOIL.cash", "GBPUSD", "LVMH", "ETHUSD"]

BACKTEST_MOIS = 12
TOP_N_CONFIGS = 5          # nombre de configs gardées après l'optimisation MT4
N_BLOCS = 4                # 12 mois -> 4 blocs de 3 mois (bloc 0 = entraînement seul)
EMBARGO_HEURES = 48        # trou entre train et test (un trade dure plus qu'un tick)

FEATURES = ["hour", "day_of_week", "rr", "side", "atr_norm", "dist_sma50_pct",
            "dist_sma200_pct", "bb_position", "rsi_h4", "dist_zone_pct"]

SEUILS_GRILLE = np.arange(0.40, 0.76, 0.05)
MIN_TRADES_SELECTION = 40

# Portes de validation sur le bloc final (jamais utilisé pour choisir config ni seuil)
GATES = {
    "min_trades_holdout": 30,
    "min_profit_factor": 1.3,
    "min_recovery_factor": 2.0,    # profit net / drawdown max
    "min_auc_oos": 0.55,
    # Le filtre doit faire mieux que "sans modèle" en qualité (PF et recovery),
    # pas en profit absolu : prendre moins de trades baisse mécaniquement le total.
    "ameliore_vs_baseline": True,
}


# ──────────────────────── [STUB] Interface MT4 ───────────────────────────
def explorer_configs(asset, date_from, date_to, top_n):
    """[STUB] Lance l'optimisation MT4 (MT4_optimisation_function) et retourne
    top_n configs sous la forme [{"id": "cfg01", "set_file": "...", "score": 1.23}, ...].
    Aujourd'hui MT4.py n'en garde qu'une (combin_found) : à étendre pour en garder N."""
    raise NotImplementedError


def backtest_avec_logs(asset, config, date_from, date_to, out_dir):
    """[STUB] Un backtest simple (pas une optimisation) avec la config, EA en mode log :
    il écrit TOUS les signaux (pris ou non) dans out_dir/signals.csv. Un seul processus
    MT4 à la fois sur ce fichier -> pas de conflit d'écriture. Retourne le chemin du CSV."""
    raise NotImplementedError


def backtest_avec_modele(asset, config, date_from, date_to, scored_csv):
    """[STUB] Backtest MT4 où l'EA lit scored_csv (time;symbol;side;proba) et ne prend
    le signal que si proba >= seuil. WebRequest n'étant pas disponible dans le
    Strategy Tester, la prédiction est pré-calculée en Python. Retourne un dict de stats."""
    raise NotImplementedError


def deployer(asset, config, model_path, seuil):
    """[STUB] Copie le .set dans MQL4/Presets, le modèle dans le dossier du serveur Flask,
    écrit le seuil, puis relance MT4 (logique de manage_real_mt4_during_night)."""
    raise NotImplementedError


# ───────────────────────────── Dataset ───────────────────────────────────
def construire_dataset(csv_par_config):
    """csv_par_config : {config_id: chemin_csv}. Concatène et prépare target."""
    frames = []
    for config_id, path in csv_par_config.items():
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)
        df["config_id"] = config_id
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M", errors="coerce")
    if df["side"].dtype == object:
        df["side"] = df["side"].map({"BUY": 1, "SELL": 0}).fillna(df["side"])
    for col in FEATURES + ["resultat"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["time", "resultat"]).sort_values("time").reset_index(drop=True)
    df["target"] = (df["resultat"] > 0).astype(int)
    return df


# ────────────────────────── Walk-forward (OOF) ───────────────────────────
def make_model(y_train):
    n_neg, n_pos = int((y_train == 0).sum()), int((y_train == 1).sum())
    # Petit modèle, nombre d'arbres FIXE : pas d'early stopping sur le test (fuite).
    return xgb.XGBClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=3, min_child_weight=10,
        subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
        scale_pos_weight=n_neg / max(n_pos, 1),
        tree_method="hist", eval_metric="logloss", n_jobs=-1, random_state=42)


def proba_out_of_fold(df, n_blocs=N_BLOCS, embargo_heures=EMBARGO_HEURES):
    """Découpe PAR DATE (pas par ligne : plusieurs configs partagent les mêmes dates).
    Bloc b>=1 : modèle entraîné sur les dates < début du bloc b - embargo.
    Retourne (df avec colonnes 'bloc' et 'proba_oof', liste des AUC par bloc)."""
    # Temps en secondes depuis le 1er signal : indépendant de la résolution
    # (ns/us) choisie par la version de pandas.
    t = (df["time"] - df["time"].min()).dt.total_seconds().to_numpy()
    bornes = np.linspace(0.0, t.max() + 1.0, n_blocs + 1)
    embargo = embargo_heures * 3600.0
    df = df.copy()
    df["bloc"] = np.clip(np.digitize(t, bornes[1:-1]), 0, n_blocs - 1)
    df["proba_oof"] = np.nan

    X, y, aucs = df[FEATURES].fillna(0.0), df["target"], []
    for b in range(1, n_blocs):
        tr = t < (bornes[b] - embargo)
        te = df["bloc"].to_numpy() == b
        if tr.sum() < 100 or y[tr].nunique() < 2 or te.sum() == 0:
            continue
        model = make_model(y[tr])
        model.fit(X[tr], y[tr])
        df.loc[te, "proba_oof"] = model.predict_proba(X[te])[:, 1]
        if y[te].nunique() == 2:
            aucs.append(roc_auc_score(y[te], df.loc[te, "proba_oof"]))
    return df, aucs


# ───────────────────────────── Évaluation ────────────────────────────────
def stats_trades(resultats):
    r = np.asarray(resultats, dtype=float)
    if len(r) == 0:
        return {"n": 0, "profit": 0.0, "pf": 0.0, "dd": 0.0, "recovery": 0.0, "wr": 0.0}
    gains, pertes = r[r > 0].sum(), -r[r < 0].sum()
    cum = np.cumsum(r)
    dd = float((np.maximum.accumulate(cum) - cum).max())
    profit = float(r.sum())
    return {"n": int(len(r)), "profit": profit,
            "pf": float(gains / pertes) if pertes > 0 else float("inf"),
            "dd": dd, "recovery": profit / dd if dd > 0 else float("inf"),
            "wr": float((r > 0).mean())}


def choisir_seuil(df_sel):
    """Seuil au meilleur profit factor sur les blocs de sélection (assez de trades)."""
    meilleur, pf_max = None, 0.0
    for s in SEUILS_GRILLE:
        st = stats_trades(df_sel.loc[df_sel["proba_oof"] >= s, "resultat"])
        if st["n"] >= MIN_TRADES_SELECTION and st["pf"] > pf_max:
            meilleur, pf_max = float(s), st["pf"]
    return meilleur, pf_max


def verifier(holdout_modele, holdout_baseline, aucs):
    """Retourne (ok, raisons_echec)."""
    raisons = []
    auc_oos = float(np.mean(aucs)) if aucs else 0.0
    if holdout_modele["n"] < GATES["min_trades_holdout"]:
        raisons.append(f"trop peu de trades ({holdout_modele['n']})")
    if holdout_modele["pf"] < GATES["min_profit_factor"]:
        raisons.append(f"profit factor {holdout_modele['pf']:.2f}")
    if holdout_modele["recovery"] < GATES["min_recovery_factor"]:
        raisons.append(f"recovery factor {holdout_modele['recovery']:.2f}")
    if auc_oos < GATES["min_auc_oos"]:
        raisons.append(f"AUC OOS {auc_oos:.3f}")
    if GATES["ameliore_vs_baseline"] and (
            holdout_modele["pf"] < holdout_baseline["pf"]
            or holdout_modele["recovery"] < holdout_baseline["recovery"]):
        raisons.append("le filtre n'améliore pas PF/recovery par rapport au baseline")
    return len(raisons) == 0, raisons


# ───────────────────────────── Pipeline ──────────────────────────────────
def pipeline_asset(asset):
    run_dir = WORK_DIR / asset / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    date_to = datetime.now()
    date_from = date_to - relativedelta(months=BACKTEST_MOIS)
    rapport = {"asset": asset, "from": str(date_from.date()), "to": str(date_to.date())}

    # 1-2. Optimisation MT4 puis un backtest loggé par config (un dossier par config)
    configs = explorer_configs(asset, date_from, date_to, TOP_N_CONFIGS)
    csvs = {c["id"]: backtest_avec_logs(asset, c, date_from, date_to, run_dir / c["id"])
            for c in configs}

    # 3. Dataset + prédictions walk-forward (aucune ligne n'est scorée par un modèle qui l'a vue)
    df = construire_dataset(csvs)
    df_oof, aucs = proba_out_of_fold(df)
    rapport["auc_par_bloc"] = [round(a, 4) for a in aucs]
    df_oof.to_csv(run_dir / "dataset_oof.csv", sep=";", index=False)

    # 4. Choix de la config + seuil sur les blocs de sélection (1 .. N-2)
    sel = df_oof[(df_oof["bloc"] >= 1) & (df_oof["bloc"] < N_BLOCS - 1)]
    meilleur = None
    for c in configs:
        seuil, pf = choisir_seuil(sel[sel["config_id"] == c["id"]])
        if seuil is not None and (meilleur is None or pf > meilleur["pf"]):
            meilleur = {"config": c, "seuil": seuil, "pf": pf}
    if meilleur is None:
        rapport["decision"] = "REJET : aucune config n'a assez de trades filtrés"
        (run_dir / "report.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False))
        return False

    # 5. Juge final : dernier bloc, jamais vu pour choisir config/seuil
    cid = meilleur["config"]["id"]
    hold = df_oof[(df_oof["bloc"] == N_BLOCS - 1) & (df_oof["config_id"] == cid)]
    st_modele = stats_trades(hold.loc[hold["proba_oof"] >= meilleur["seuil"], "resultat"])
    st_base = stats_trades(hold["resultat"])
    ok, raisons = verifier(st_modele, st_base, aucs)
    rapport.update({"config": cid, "seuil": meilleur["seuil"], "holdout_modele": st_modele,
                    "holdout_baseline": st_base, "raisons_echec": raisons})

    # 6. Confirmation dans le vrai Strategy Tester (EA lit le CSV de probas OOF)
    if ok:
        scored = run_dir / "signals_scored.csv"
        out = df_oof.loc[(df_oof["config_id"] == cid) & df_oof["proba_oof"].notna(),
                         ["time", "symbol", "side", "proba_oof"]]
        out.to_csv(scored, sep=";", index=False)
        t_hold = df_oof.loc[df_oof["bloc"] == N_BLOCS - 1, "time"]
        rapport["backtest_mt4_holdout"] = backtest_avec_modele(
            asset, meilleur["config"], t_hold.min(), t_hold.max(), scored)

        # 7. Modèle final : réentraîné sur toute la période, déployé avec la config
        d = df_oof[df_oof["config_id"] == cid]
        final = make_model(d["target"])
        final.fit(d[FEATURES].fillna(0.0), d["target"])
        model_path = run_dir / "model.pkl"
        joblib.dump(final, model_path)
        joblib.dump(FEATURES, run_dir / "model_features.pkl")
        deployer(asset, meilleur["config"], model_path, meilleur["seuil"])

    rapport["decision"] = "DEPLOYE" if ok else "REJET : " + " ; ".join(raisons)
    (run_dir / "report.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False, default=str))
    print(f"[{asset}] {rapport['decision']}")
    return ok


def main(actifs=ACTIFS):
    """Un actif après l'autre : s'il est rejeté, on passe au suivant."""
    for asset in actifs:
        try:
            pipeline_asset(asset)
        except NotImplementedError:
            raise
        except Exception as e:
            print(f"[{asset}] erreur pipeline : {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
