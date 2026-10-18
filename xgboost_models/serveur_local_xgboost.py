from asyncio import sleep
import time
from flask import Flask, request, jsonify
import joblib
import numpy as np
import csv

app = Flask(__name__)

MODEL = joblib.load("xgboost_model_v3_target.pkl")
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
    data = request.json
    if data is None:
        print(f"Erreur : JSON manquant dans la requête {request.data}", flush=True)
        return jsonify({"error": "JSON manquant"}), 400

    print(f"Requête reçue : {data}", flush=True)

    if (data == "PROCESSING TEST.."):
        print("Test de traitement en cours...", flush=True)
        time.sleep(1)
        return jsonify({"status": "processing test completed"})

    row = [float(data.get(f, 0)) for f in FEATURES]
    X = np.array([row])

    #proba = float(CALIBRATOR.predict(MODEL.predict_proba(X)[:, 1]))
    proba = float(MODEL.predict_proba(X)[0, 1])

    signal = 1 if proba >= 0.00 else 0

    #if signal == 1:
    #    with open(CSV_BACKTEST, "a", newline="", encoding="utf-8-sig") as f:
    #        writer = csv.writer(f, delimiter=";")
    #
    #        writer.writerow([proba])

    print(f"Prediction : proba={proba}, signal={signal}", flush=True)

    return jsonify({
        "proba": round(proba, 4),
        "signal": signal,
        "features_used": len(FEATURES)
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
