from asyncio import sleep
import time
from flask import Flask, request, jsonify
import joblib
import numpy as np
import csv

app = Flask(__name__)

package = None
statut  = True
FEATURES = [
        'day_of_week', 'hour', 'minutes', 'trend',
        'rr', 'side', 'anticipation', 'chart_patern', 'strat_trend',
        'patern_candle', 'analyse_area', 'hedge_strat', 'sma_50',
        'sma_200', 'bollinger', 'width_BB', 
        'atr', 'rsi',
    ]
CSV_BACKTEST = "backtest_models_V3.csv"
#CALIBRATOR = joblib.load("xgboost_model_v3_target_calibrator.pkl")

@app.route("/",  methods=["GET", "POST"])
@app.route("/health",  methods=["GET", "POST"])
def health():
    print("Santé du service vérifiée", flush=True)
    return jsonify({
        "status": "ok",
        "features": len(FEATURES),
        "model_loaded": True, 
        "last request": request.method
    })

@app.route("/predict",  methods=["GET", "POST"])
def predict():
    global statut
    data = request.json
    if data is None:
        print(f"Erreur : JSON manquant dans la requête {request.data}", flush=True)
        return jsonify({"error": "JSON manquant"}), 400

    print(f"Requête reçue : {data}", flush=True)

    if (data == "PROCESSING TEST.."):
        print("Test de traitement en cours...", flush=True)
        time.sleep(1)
        return jsonify({"status": "processing test completed"})

    model = package['model']
    feature_cols = package['features']
    optimal_threshold = package['optimal_threshold']

    row = [float(data.get(f, 0)) for f in feature_cols]
    X = np.array([row])

    print(f"Test de traitement en cours...  {feature_cols}", flush=True)

    proba = float(model.predict_proba(X)[0, 1])

    signal = 1 if proba >= optimal_threshold else 0

    print(f"Prediction : proba={proba}, signal={signal}", flush=True)

    statut = True

    print(f"Pack : {package}", flush=True)
    return jsonify({
        "proba": round(proba, 4),
        "signal": signal,
        "features_used": len(feature_cols)
    })


@app.route("/asset",  methods=["GET", "POST"])
def asset():
    global package
    global statut

    if statut != True:
        print(f"Process en cours ... {statut}", flush=True)
        return jsonify({"error": "Attendre un peu et reessayer"}), 400

    data = request.json
    if data is None:
        print(f"Erreur : JSON manquant dans la requête {request.data}", flush=True)
        return jsonify({"error": "JSON manquant"}), 400

    print(f"Requête reçue : {data}", flush=True)

    if (data == "PROCESSING TEST.."):
        print("Test de traitement en cours...", flush=True)
        time.sleep(1)
        return jsonify({"status": "processing test completed"})

    filename = f"xgboost_model_v3_package{data}.pkl"

    package = joblib.load(filename)
    statut  = False

    print(package, flush=True)

    return jsonify({
        "status": "success",
        "asset": data,
        "filename": filename
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
