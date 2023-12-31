#!/usr/bin/env python

import os
import json
import redis
import pickle
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
from scipy.spatial.distance import cityblock

app = Flask(__name__)
CORS(app)

redis_conn = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

# Definir las rutas a los archivos CSV y binario
csv_path = '/shared_data/movie.csv'
bin_path = '/shared_data/movie.bin'

@app.route("/")
def index():
    return "Usage: http://<hostname>[:<prt>]/api/<url>"

@app.route('/api/csv', methods=['POST'])
def recibir_csv():
    global csv_path
    if request.method == 'POST':
        data = request.get_json()
        nombre = data.get('obj')
        df = pd.DataFrame(nombre)
        df.to_csv(csv_path, index=False)
        df.to_pickle(bin_path)  # Utilizamos to_pickle en lugar de to_bin
        redis_conn.set('csv', json.dumps(nombre))
        return jsonify({"csv cargado correctamente a redis"})
    else:
        return jsonify({"mensaje": "Esta ruta solo acepta solicitudes POST"})

@app.route('/api/bin', methods=['POST'])
def recibir_bin():
    global bin_path
    if request.method == 'POST':
        data = request.get_json()
        movie = data.get('obj')
        df = pd.DataFrame(movie)
        df.to_pickle(bin_path)
        redis_conn.set('bin', json.dumps(movie))
        return jsonify({"bin cargado correctamente a redis"})
    else:
        return jsonify({"mensaje": "Esta ruta solo acepta solicitudes POST"})

@app.route('/api/valor', methods=['POST'])
def recibir_datos():
    global valoresfinal, peliculasp
    if request.method == 'POST':
        data = request.get_json()

        col1 = data.get('col1')
        col2 = data.get('col2')
        col3 = data.get('col3')

        numero = data.get('numero')
        numerox = int(numero)
        bin_path = '/shared_data/movie.bin'

        try:
            with open(bin_path, 'rb') as movie:
                af = pickle.load(movie)
        except FileNotFoundError:
            # Manejar el caso en el que el archivo no existe
            af = pd.DataFrame()

        peli = af

        # Imprimir las columnas del DataFrame
        print(peli.columns)

        # Verificar si col3 está presente en las columnas del DataFrame
        if col3 not in peli.columns:
            return jsonify({"error": f"La columna {col3} no está presente en el DataFrame"})

        peli[col3] = pd.to_numeric(peli[col3], errors='coerce')
        peli[col1] = pd.to_numeric(peli[col1], errors='coerce')

        consolidated_dfmi = columnas(peli, col1, col2, col3)
        consolidated_dfmi = pd.concat([consolidated_dfmi.query(f'userId == {numerox}'), consolidated_dfmi.head(1000)])
        consolidated_dfmi = consolidated_dfmi.loc[~consolidated_dfmi.index.duplicated(keep='first')]
        consolidated_dfmi = consolidated_dfmi.fillna(0)

        def computeNearestNeighbor(dataframe, target_user, distance_metric=cityblock):
            distances = np.zeros(len(dataframe))
            target_row = dataframe.loc[target_user]
            for i, (index, row) in enumerate(dataframe.iterrows()):
                if index == target_user:
                    continue

                non_zero_values = (target_row != 0) & (row != 0)
                distance = distance_metric(target_row[non_zero_values].fillna(0), row[non_zero_values].fillna(0))
                distances[i] = distance

            sorted_indices = np.argsort(distances)
            sorted_distances = distances[sorted_indices]
            return list(zip(dataframe.index[sorted_indices], sorted_distances))

        target_user_id = numerox
        neighborsmi = computeNearestNeighbor(consolidated_dfmi, target_user_id)
        diccionario_resultante = dict(neighborsmi)
        valoresfinal = diccionario_resultante

        cd2 = pd.DataFrame(neighborsmi)
        cd2.columns = ['Id_user', 'Distancias']

        primeros = cd2['Id_user'].unique().tolist()[:10]
        resul = peli.query('userId in @primeros')
        newx = resul.query('rating == 5.0')['movieId'].drop_duplicates()
        dictionary_final = dict(zip(newx.index, newx.values))
        peliculasp = dictionary_final

        redis_conn.set('valoresfinal', json.dumps(valoresfinal))
        redis_conn.set('peliculas', json.dumps(peliculasp))

        return jsonify(valoresfinal)
    else:
        return jsonify({"mensaje": "Esta ruta solo acepta solicitudes POST"})

@app.route('/api/valor', methods=['GET'])
def get_users():
    cached_data = redis_conn.get('valoresfinal')
    if cached_data:
        return jsonify(json.loads(cached_data))
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})

@app.route('/api/peliculas', methods=['GET'])
def get_peliculas():
    peliculas_cached = redis_conn.get('peliculas')
    if peliculas_cached:
        peliculas = json.loads(peliculas_cached)
        return jsonify(peliculas)
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})

@app.route('/api/csv', methods=['GET'])
def get_csv():
    csv_cached = redis_conn.get('csv')
    if csv_cached:
        csvx = json.loads(csv_cached)
        return jsonify(csvx)
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})

@app.route('/api/bin', methods=['GET'])
def get_bin():
    bin_cached = redis_conn.get('bin')
    if bin_cached:
        binx = json.loads(bin_cached)
        return jsonify(binx)
    else:
        return jsonify({"mensaje": "No hay valores finales almacenados en Redis"})

@app.route('/api/mostrar_bin', methods=['GET'])
def mostrar_bin():
    try:
        return send_file(bin_path, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"mensaje": "El archivo movie.bin no se encuentra"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0")

