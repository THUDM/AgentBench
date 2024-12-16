# import requests
# from datetime import datetime
#
# # Base FHIR URL for your system
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
#
# def post_service_request(mrn, referral_text, snomed_code, display_text):
#     # Define the URL for ServiceRequest
#     url = f'{fhir_base_url}ServiceRequest'
#
#     # Fetch the current entries from the FHIR server to determine the highest current ID
#     response = requests.get(url)
#
#     if response.status_code != 200:
#         print(f"Error fetching existing ServiceRequests: {response.status_code}")
#         return "Error fetching existing entries"
#
#     data = response.json()
#
#     # Find the highest entry ID
#     existing_ids = [int(entry['resource']['id']) for entry in data['entry'] if entry['resource']['id'].isdigit()]
#     new_entry_id = max(existing_ids) + 1 if existing_ids else 1
#
#     # Prepare the new ServiceRequest entry with SNOMED code and display
#     new_entry = {
#         "resourceType": "ServiceRequest",
#         "id": str(new_entry_id),  # Assign the calculated ID
#         "status": "active",  # The status of the service request
#         "intent": "order",  # The intent of the request (an order)
#         "code": {
#             "coding": [
#                 {
#                     "system": "http://snomed.info/sct",  # SNOMED CT system URL
#                     "code": snomed_code,  # SNOMED code from input
#                     "display": display_text  # Display text from input
#                 }
#             ],
#             "text": display_text  # Free text description
#         },
#         "subject": {
#             "identifier": {
#                 "system": "http://terminology.hl7.org/CodeSystem/v2-0203",  # Identifier system
#                 "value": mrn  # Patient's MRN
#             }
#         },
#         "authoredOn": datetime.now().isoformat(),  # Current timestamp
#         "note": [
#             {
#                 "text": referral_text  # Referral details (free text)
#             }
#         ]
#     }
#
#     # Define the request body as a Bundle with the new entry
#     bundle = {
#         "resourceType": "Bundle",
#         "type": "transaction",
#         "entry": [
#             {
#                 "resource": new_entry
#             }
#         ]
#     }
#
#     try:
#         # Make the POST request to create the ServiceRequest
#         response = requests.post(url, json=bundle)
#         response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
#
#         # If the request is successful, return 'done'
#         if response.status_code == 201:
#             return "done"
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
# referral_text = "Acute left knee injury, imaging showing ACL tear."  # Referral details (free text)
# snomed_code = "306181000000106"  # SNOMED code for orthopedic surgery referral
# display_text = "Order orthopedic surgery referral"  # Display text for the code
#
# # Call the function and print the result
# result = post_service_request(mrn, referral_text, snomed_code, display_text)
# print(result)

import requests
from datetime import datetime
from typing import Dict

def ref_sol7(method: str, url: str, payload: Dict, task_id: int) -> bool:
    """
    Create a new ServiceRequest for a patient and verify the request was successful.

    Args:
        method (str): The HTTP method ('POST').
        url (str): The API endpoint for the ServiceRequest resource.
        payload (dict): The data including MRN, referral details, SNOMED code, and display text.
        task_id (int): The task ID for tracking purposes.

    Returns:
        bool: True if the request was successful, False otherwise.
    """
    if method.lower() != "post":
        print("Error: Only POST method is supported.")
        return False

    try:
        # Extract necessary data from the payload
        mrn = payload.get('mrn')
        referral_text = payload.get('referral_text')
        snomed_code = payload.get('snomed_code')
        display_text = payload.get('display_text')

        if not all([mrn, referral_text, snomed_code, display_text]):
            print("Error: Missing required fields in payload.")
            return False

        # Prepare the ServiceRequest entry
        url = f'{url}ServiceRequest'

        # Fetch existing entries to calculate the next ID
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching existing ServiceRequests: {response.status_code}")
            return False

        data = response.json()
        existing_ids = [int(entry['resource']['id']) for entry in data['entry'] if entry['resource']['id'].isdigit()]
        new_entry_id = max(existing_ids) + 1 if existing_ids else 1

        new_entry = {
            "resourceType": "ServiceRequest",
            "id": str(new_entry_id),
            "status": "active",
            "intent": "order",
            "code": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": snomed_code,
                        "display": display_text
                    }
                ],
                "text": display_text
            },
            "subject": {
                "identifier": {
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "value": mrn
                }
            },
            "authoredOn": datetime.now().isoformat(),
            "note": [
                {
                    "text": referral_text
                }
            ]
        }

        # Define the request body as a Bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {"resource": new_entry}
            ]
        }

        # Perform the POST request
        post_response = requests.post(url, json=bundle)
        post_response.raise_for_status()

        if post_response.status_code == 201:
            print("ServiceRequest created successfully")
            return True
        else:
            print(f"Error: Received status code {post_response.status_code} - {post_response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return False

# Example usage of ref_sol7
if __name__ == "__main__":
    fhir_base_url = "http://34.132.86.17:8080/fhir/"
    service_request_url = f"{fhir_base_url}"

    # Example payload
    payload = {
        "mrn": "S1023381",
        "referral_text": "Acute left knee injury, imaging showing ACL tear.",
        "snomed_code": "306181000000106",
        "display_text": "Order orthopedic surgery referral"
    }

    # Call ref_sol7 with POST method
    task_id = 12345
    result = ref_sol7("POST", service_request_url, payload, task_id)
    print(result)  # Expected output: True or False
