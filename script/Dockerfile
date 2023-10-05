# Använd en Python-basbild
FROM python:3.9-slim
RUN pip install pymongo

# Skapa en arbetskatalog
WORKDIR /app

# Kopiera seedningsskriptet och kravfilen (om det finns) till arbetskatalogen
COPY seed.py .
# Om du har ett kravfil (requirements.txt), kopiera det och installera beroenden
# COPY requirements.txt .
# RUN pip install -r requirements.txt

# Ange kommandot som ska köras när containern startar
CMD ["python", "seed.py"]