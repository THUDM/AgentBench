# import requests
# from datetime import datetime
# import re
#
# # Base FHIR URL for your system
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
#
# def post_medication_request(mrn, dosage_instruction_text, dose_value, dose_unit, medication_codeable_concept):
#     # Define the URL for MedicationRequest
#     url = f'{fhir_base_url}MedicationRequest'
#
#     # Fetch the existing bundle and its entries to find the maximum entry ID
#     # Assuming we have the current bundle data (here we're just simulating it)
#     # You should fetch this from the FHIR server with a GET request or keep it in memory
#     response = requests.get(f"{fhir_base_url}MedicationRequest")
#
#     if response.status_code != 200:
#         return f"Error: Unable to retrieve existing MedicationRequests - {response.status_code}"
#
#     # Extract the current entries from the bundle
#     bundle = response.json()
#
#     # List to track the current entry IDs
#     existing_ids = []
#
#     # Iterate over the existing entries to extract the numeric part of the IDs
#     for entry in bundle.get('entry', []):
#         match = re.search(r'(\d+)', entry['fullUrl'])  # Extract numbers from the URL (e.g., 'MedicationRequest/39054')
#         if match:
#             existing_ids.append(int(match.group(1)))  # Append the numeric ID to the list
#
#     # Calculate the new entry ID by finding the max of existing IDs and adding 1
#     new_entry_id = max(existing_ids, default=0) + 1  # Default to 0 if no entries exist
#
#     # Prepare the new entry that will be added to the 'entry' list
#     new_entry = {
#         "fullUrl": f"{fhir_base_url}MedicationRequest/{new_entry_id}",  # New entry URL with calculated ID
#         "resource": {
#             "status": "active",  # This assumes the medication request is active
#             "intent": "order",
#             "medicationCodeableConcept": {
#                 "text": medication_codeable_concept  # The medication passed in the input
#             },
#             "subject": {
#                 "identifier": {
#                     "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
#                     "value": mrn  # Patient's MRN
#                 }
#             },
#             "authoredOn": datetime.now().isoformat(),  # Current timestamp
#             "dosageInstruction": [
#                 {
#                     "text": dosage_instruction_text,
#                     "timing": {
#                         "code": {
#                             "text": dosage_instruction_text  # Dosage instruction text
#                         }
#                     },
#                     "doseAndRate": [
#                         {
#                             "doseQuantity": {
#                                 "value": dose_value,  # Dosage value (quantity)
#                                 "unit": dose_unit  # Unit (e.g., mg, mL)
#                             }
#                         }
#                     ]
#                 }
#             ]
#         },
#         "search": {
#             "mode": "match"
#         }
#     }
#
#     # Define the request body as a Bundle with the new entry
#     bundle = {
#         "resourceType": "Bundle",
#         "type": "transaction",
#         "entry": [new_entry]  # Append the new entry into the 'entry' list
#     }
#
#     try:
#         # Make the POST request to create the MedicationRequest
#         response = requests.post(url, json=bundle)
#         response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
#
#         # If the request is successful, return the full URL of the newly created resource
#         if response.status_code == 201:
#             new_entry_response = response.json()
#             return new_entry_response.get('entry', [{}])[0].get('fullUrl', 'URL not available')
#         else:
#             return f"Error: {response.status_code} - {response.text}"
#
#     except requests.exceptions.RequestException as e:
#         print(f"An error occurred: {e}")
#         return "Error making the POST request"
#
#
# # test:
# mrn = "S1023381"  # Example MRN
# dosage_instruction_text = "BID"  # Dosage instruction (e.g., "twice a day")
# dose_value = 350  # Dosage amount (e.g., 350)
# dose_unit = "mg"  # Unit of measurement (e.g., mg)
# medication_codeable_concept = "carisoprodol (Soma) 350 mg tablet"  # Example medication
#
# # Call the function and print the result
# result = post_medication_request(mrn, dosage_instruction_text, dose_value, dose_unit, medication_codeable_concept)
# print(result)

import requests
from datetime import datetime
import re

def ref_sol5(method: str, url: str, payload: dict, task_id: int) -> bool:
    """
    Create a new MedicationRequest for a patient using the API function.

    Args:
        method (str): The HTTP method ('POST').
        url (str): The API endpoint for the MedicationRequest resource.
        payload (dict): The data including MRN, dosage instructions, dose, and medication information.
        task_id (int): The task ID for tracking purposes.

    Returns:
        bool: True if the MedicationRequest is successfully created, False otherwise.
    """
    try:
        # Log the request details (for debugging purposes)
        print(f"Task ID: {task_id}, Method: {method}, URL: {url}, Payload: {payload}")

        if method != "POST":
            raise ValueError("Invalid method. Use 'POST' for this function.")

        # Extract the necessary fields from the payload
        mrn = payload.get('mrn')
        dosage_instruction_text = payload.get('dosage_instruction_text')
        dose_value = payload.get('dose_value')
        dose_unit = payload.get('dose_unit')
        medication_codeable_concept = payload.get('medication_codeable_concept')

        if not all([mrn, dosage_instruction_text, dose_value, dose_unit, medication_codeable_concept]):
            return False  # Return False if any required field is missing

        # Perform a GET request to retrieve existing MedicationRequests
        get_response = requests.get(url)
        get_response.raise_for_status()
        bundle = get_response.json()

        # Extract existing IDs to calculate the new entry ID
        existing_ids = []
        for entry in bundle.get('entry', []):
            match = re.search(r'(\d+)', entry['fullUrl'])  # Extract numbers from the fullUrl
            if match:
                existing_ids.append(int(match.group(1)))

        new_entry_id = max(existing_ids, default=0) + 1

        # Create the new MedicationRequest entry
        new_entry = {
            "fullUrl": f"{url}/{new_entry_id}",
            "resource": {
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "text": medication_codeable_concept
                },
                "subject": {
                    "identifier": {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "value": mrn
                    }
                },
                "authoredOn": datetime.now().isoformat(),
                "dosageInstruction": [
                    {
                        "text": dosage_instruction_text,
                        "timing": {
                            "code": {
                                "text": dosage_instruction_text
                            }
                        },
                        "doseAndRate": [
                            {
                                "doseQuantity": {
                                    "value": dose_value,
                                    "unit": dose_unit
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

        # Prepare the bundle with the new entry
        new_bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [new_entry]
        }

        # Perform the POST request to create the new MedicationRequest
        post_response = requests.post(url, json=new_bundle)
        post_response.raise_for_status()

        if post_response.status_code == 201:
            return True  # Successfully created the MedicationRequest
        else:
            return False  # Return False if the POST request failed

    except requests.exceptions.RequestException as e:
        print(f"Task ID: {task_id}, An error occurred: {e}")
        return False  # Return False in case of an exception

# Example usage
if __name__ == "__main__":
    fhir_base_url = "http://34.132.86.17:8080/fhir/"
    medication_request_url = f"{fhir_base_url}MedicationRequest"

    # Test payload
    payload = {
        "mrn": "S1023381",
        "dosage_instruction_text": "BID",
        "dose_value": 350,
        "dose_unit": "mg",
        "medication_codeable_concept": "carisoprodol (Soma) 350 mg tablet"
    }

    print(ref_sol5("POST", medication_request_url, payload, 401))  # Expected output: True or False
