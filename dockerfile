# Use uma imagem base do Python
FROM python:3.9-slim

# Instale as bibliotecas do sistema necessárias
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*  # Limpeza do cache do apt

# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copie o arquivo de requisitos para o diretório de trabalho
COPY requirements.txt ./

# Instale as dependências listadas no requirements.txt
RUN pip install --no-cache-dir -v -r requirements.txt

# Copie todo o código da aplicação para o diretório de trabalho
COPY . .

# Exponha a porta que a aplicação usará
EXPOSE 5000

# Comando para executar a aplicação
CMD ["python", "lerPlaca2.py"]
