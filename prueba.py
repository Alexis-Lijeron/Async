import requests

url = "http://localhost:8000/api/v1/estudiantes/?priority=5"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTgxMjMzMzQsInN1YiI6IlZJQzAwMSJ9.yw2Zniuhaf_mpKREWfKYOYBWy2UBmHLP7_VVNhaIb94",
    "Content-Type": "application/json"
}

for i in range(1, 100000000):
    data = {
        "registro": f"2025{i:03d}",
        "nombre": f"Estudiante{i}",
        "apellido": "Prueba",
        "ci": f"CI{i:05d}",
        "contraseña": "pass123",
        "carrera_id": 1,
        
    "carrera_codigo":"INF187"
    }
    r = requests.post(url, json=data, headers=headers)
    print(r.json())
