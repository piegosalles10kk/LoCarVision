import os
import cv2
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
from ultralytics import YOLO
import base64
from google.cloud import vision
import re

# Caminho do arquivo de chave do Google
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "models/chave.json"  # Ajuste esse caminho se necessário

# Inicialização dos modelos YOLO
model_carros = YOLO('models/yolov8_carros.pt')
model_placas = YOLO('models/yolov8_placas.pt')

# Configuração da aplicação Flask
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FILENAME = 'imagem_atual.jpg'

# Classe para detecção de objetos (carros e placas)
class ObjectDetector:
    def __init__(self, model_carros_path='models/yolov8_carros.pt', model_placas_path='models/yolov8_placas.pt'):
        self.model_carros = YOLO(model_carros_path)
        self.model_placas = YOLO(model_placas_path)

    def detectar_carros(self, imagem):
        resultados = self.model_carros(imagem)
        return resultados[0].boxes.xyxy

    def detectar_placas(self, crop_imagem):
        resultados = self.model_placas(crop_imagem)
        return resultados[0].boxes.xyxy

# Função para converter a imagem cropada em base64
def crop_para_base64(crop_imagem):
    retval, buffer = cv2.imencode('.jpg', crop_imagem)
    return base64.b64encode(buffer).decode('utf-8')

# Função para processar o texto da placa usando regex
def processar_texto_placa(texto_detectado):
    # Remover espaços e traços do texto detectado
    texto_limpo = texto_detectado.replace(" ", "").replace("-", "")
    
    # Regex aprimorada para capturar placas antigas (ABC1234) e Mercosul (ABC1D23)
    padrao_placa = re.compile(r'([A-Za-z]{3}[0-9]{1}[A-Za-z]{1}[0-9]{2}|[A-Za-z]{3}[0-9]{4})')
    correspondencia = padrao_placa.search(texto_limpo)
    
    if correspondencia:
        return correspondencia.group(0)  # Retorna o padrão encontrado
    return None

# Função para enviar a imagem para o Google Vision e processar o texto da placa
def enviar_para_google_vision(crop_imagem):
    client = vision.ImageAnnotatorClient()
    _, buffer = cv2.imencode('.jpg', crop_imagem)
    image = vision.Image(content=buffer.tobytes())
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        # Pega todo o texto detectado na imagem
        texto_detectado = texts[0].description.strip().replace("\n", "")
        # Processa o texto para extrair a placa
        texto_placa = processar_texto_placa(texto_detectado)
        return texto_placa
    return None

# Inicialização da classe de detecção de objetos
object_detector = ObjectDetector()

# Função principal de processamento de imagem
def processar_imagem(imagem):
    todas_as_placas = []
    crops_base64 = []

    # Detecta os carros na imagem
    caixas_carros = object_detector.detectar_carros(imagem)

    for carro in caixas_carros:
        x1, y1, x2, y2 = map(int, carro)
        crop_carro = imagem[y1:y2, x1:x2]
        cv2.rectangle(imagem, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # Detecta as placas no carro
        caixas_placas = object_detector.detectar_placas(crop_carro)

        if caixas_placas is not None and len(caixas_placas) > 0:
            for placa in caixas_placas:
                px1, py1, px2, py2 = map(int, placa)
                crop_placa = crop_carro[py1:py2, px1:px2]

                # Envia a placa para o Google Vision e processa o texto detectado
                texto_placa = enviar_para_google_vision(crop_placa)
                if texto_placa:
                    todas_as_placas.append(texto_placa)
                    crop_base64 = crop_para_base64(crop_placa)
                    crops_base64.append(crop_base64)

                # Desenha a caixa da placa na imagem original
                cv2.rectangle(imagem, (px1 + x1, py1 + y1), (px2 + x1, py2 + y1), (0, 255, 0), 2)

    return todas_as_placas, imagem, crops_base64

# Endpoint da API para upload de imagem
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(FILENAME)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    imagem = cv2.imread(filepath)
    placas_identificadas, imagem_resultado, crops_base64 = processar_imagem(imagem)
    imagem_resultado = cv2.resize(imagem_resultado, (500, 500))
    resultado_path = os.path.join(UPLOAD_FOLDER, 'resultado_' + FILENAME)

    cv2.imwrite(resultado_path, imagem_resultado)

    if placas_identificadas:
        return jsonify({
            'numero_veiculos': len(placas_identificadas),
            'placas': placas_identificadas,
            'imagem_resultado': resultado_path,
            'crops_base64': crops_base64
        }), 200

    return jsonify({
        'numero_veiculos': 0,
        'placas': [],
        'mensagem': 'Não foi localizado placa nem veículo na imagem.'
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Certifique-se de que o Flask escuta em todas as interfaces
