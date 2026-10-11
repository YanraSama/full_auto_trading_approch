from asyncio import sleep
import time
from flask import Flask, request, jsonify
import joblib
import numpy as np

app = Flask(__name__)

MODEL = joblib.load("xgboost_model_v3_target.pkl")
FEATURES = joblib.load("xgboost_model_v3_target_features.pkl")


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

    proba = float(MODEL.predict_proba(X)[0, 1])
    signal = 1 if proba >= 0.65 else 0

    print(f"Prediction : proba={proba}, signal={signal}", flush=True)

    return jsonify({
        "proba": round(proba, 4),
        "signal": signal,
        "features_used": len(FEATURES)
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
