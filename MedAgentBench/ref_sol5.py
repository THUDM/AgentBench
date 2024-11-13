import requests
from datetime import datetime
import re

# Base FHIR URL for your system
fhir_base_url = "http://34.132.86.17:8080/fhir/"


def post_medication_request(mrn, dosage_instruction_text, dose_value, dose_unit, medication_codeable_concept):
    # Define the URL for MedicationRequest
    url = f'{fhir_base_url}MedicationRequest'

    # Fetch the existing bundle and its entries to find the maximum entry ID
    # Assuming we have the current bundle data (here we're just simulating it)
    # You should fetch this from the FHIR server with a GET request or keep it in memory
    response = requests.get(f"{fhir_base_url}MedicationRequest")

    if response.status_code != 200:
        return f"Error: Unable to retrieve existing MedicationRequests - {response.status_code}"

    # Extract the current entries from the bundle
    bundle = response.json()

    # List to track the current entry IDs
    existing_ids = []

    # Iterate over the existing entries to extract the numeric part of the IDs
    for entry in bundle.get('entry', []):
        match = re.search(r'(\d+)', entry['fullUrl'])  # Extract numbers from the URL (e.g., 'MedicationRequest/39054')
        if match:
            existing_ids.append(int(match.group(1)))  # Append the numeric ID to the list

    # Calculate the new entry ID by finding the max of existing IDs and adding 1
    new_entry_id = max(existing_ids, default=0) + 1  # Default to 0 if no entries exist

    # Prepare the new entry that will be added to the 'entry' list
    new_entry = {
        "fullUrl": f"{fhir_base_url}MedicationRequest/{new_entry_id}",  # New entry URL with calculated ID
        "resource": {
            "status": "active",  # This assumes the medication request is active
            "intent": "order",
            "medicationCodeableConcept": {
                "text": medication_codeable_concept  # The medication passed in the input
            },
            "subject": {
                "identifier": {
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "value": mrn  # Patient's MRN
                }
            },
            "authoredOn": datetime.now().isoformat(),  # Current timestamp
            "dosageInstruction": [
                {
                    "text": dosage_instruction_text,
                    "timing": {
                        "code": {
                            "text": dosage_instruction_text  # Dosage instruction text
                        }
                    },
                    "doseAndRate": [
                        {
                            "doseQuantity": {
                                "value": dose_value,  # Dosage value (quantity)
                                "unit": dose_unit  # Unit (e.g., mg, mL)
                            }
                        }
                    ]
                }
            ]
        },
        "search": {
            "mode": "match"
        }
    }

    # Define the request body as a Bundle with the new entry
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [new_entry]  # Append the new entry into the 'entry' list
    }

    try:
        # Make the POST request to create the MedicationRequest
        response = requests.post(url, json=bundle)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)

        # If the request is successful, return the full URL of the newly created resource
        if response.status_code == 201:
            new_entry_response = response.json()
            return new_entry_response.get('entry', [{}])[0].get('fullUrl', 'URL not available')
        else:
            return f"Error: {response.status_code} - {response.text}"

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return "Error making the POST request"


# test:
mrn = "S1023381"  # Example MRN
dosage_instruction_text = "BID"  # Dosage instruction (e.g., "twice a day")
dose_value = 350  # Dosage amount (e.g., 350)
dose_unit = "mg"  # Unit of measurement (e.g., mg)
medication_codeable_concept = "carisoprodol (Soma) 350 mg tablet"  # Example medication

# Call the function and print the result
result = post_medication_request(mrn, dosage_instruction_text, dose_value, dose_unit, medication_codeable_concept)
print(result)
