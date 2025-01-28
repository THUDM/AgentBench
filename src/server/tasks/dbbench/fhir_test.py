import requests
import json

# FHIR server base URL
FHIR_SERVER_URL = "http://34.132.86.17:8080/fhir"

# Example FHIR resource (Patient)
patient_resource = {
    "resourceType": "Patient",
    "name": [{"family": "Doe", "given": ["John"]}],
    "gender": "male",
    "birthDate": "1990-01-01"
}

# Send a POST request to create a Patient resource
def create_patient():
    url = f"{FHIR_SERVER_URL}/Patient"
    headers = {
        "Content-Type": "application/fhir+json"
    }

    response = requests.post(url, headers=headers, data=json.dumps(patient_resource))

    if response.status_code == 201:
        print("Patient created successfully!")
        print("Location of the new resource:", response.headers["Location"])
    else:
        print(f"Failed to create patient. Status code: {response.status_code}")
        print("Response:", response.json())

# Fetch metadata from the server (e.g., CapabilityStatement)
def fetch_metadata():
    url = f"{FHIR_SERVER_URL}/metadata"
    response = requests.get(url, headers={"Accept": "application/fhir+json"})

    if response.status_code == 200:
        metadata = response.json()
        print("CapabilityStatement retrieved successfully!")
        print(json.dumps(metadata, indent=2))
    else:
        print(f"Failed to fetch metadata. Status code: {response.status_code}")

# Run the example functions
if __name__ == "__main__":
    fetch_metadata()
    create_patient()
