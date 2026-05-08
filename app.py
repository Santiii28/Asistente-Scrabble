from flask import Flask, render_template, request, jsonify
from scrabble import recomendar, construir_trie, PUNTAJES

app = Flask(__name__)
trie = construir_trie()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analizar", methods=["POST"])
def analizar():
    data = request.get_json()
    fichas_str = data.get("fichas", "").strip()

    if not fichas_str:
        return jsonify({"error": "Ingresa al menos una ficha"}), 400

    letras = fichas_str.upper().split()
    invalidas = [l for l in letras if l not in PUNTAJES]
    if invalidas:
        return jsonify({"error": f"Letras no válidas: {', '.join(invalidas)}"}), 400
    if len(letras) < 2:
        return jsonify({"error": "Ingresa al menos 2 fichas"}), 400
    if len(letras) > 7:
        return jsonify({"error": "Máximo 7 fichas (reglas Scrabble)"}), 400

    return jsonify(recomendar(fichas_str, trie))


if __name__ == "__main__":
    app.run(debug=True)
