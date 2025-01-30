# import requests
# from datetime import datetime, timedelta
#
# # Base FHIR URL for your system
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
# # Function to create a new Procedure entry
# def post_procedure_request(medication_request_id, loinc_code, loinc_display, service_request_id=None):
#     # Define the URL for Procedure creation
#     url = f'{fhir_base_url}Procedure'
#
#     # Generate a new ID for the Procedure entry (for simplicity, assuming next available integer ID)
#     # You can change this to any logic you'd like. Here it's just a static incremented ID
#     new_id = 1000  # Starting point for new procedure IDs, can be modified for dynamic handling
#
#     # Set the date for "completed" (next day if no service)
#     if service_request_id is None:
#         complete_time = (datetime.now() + timedelta(days=1)).isoformat()  # Set to the next day if no service request
#     else:
#         complete_time = datetime.now().isoformat()  # Current time if service exists
#
#     # Prepare the Procedure entry data
#     procedure_entry = {
#         "resourceType": "Procedure",
#         "id": str(new_id),  # New ID for Procedure entry
#         "status": "completed",  # Procedure status as completed
#         "code": {
#             "coding": [
#                 {
#                     "system": "http://loinc.org",  # LOINC Code System
#                     "code": loinc_code,  # LOINC Code for Serum Magnesium Test
#                     "display": loinc_display  # Display name for the test
#                 }
#             ],
#             "text": "Morning serum magnesium test"  # Free text description
#         },
#         "subject": {
#             "reference": f"Patient/{medication_request_id}"  # Reference to the Patient (using MedicationRequest ID)
#         },
#         "encounter": {
#             "reference": f"Encounter/{service_request_id}" if service_request_id else None  # Reference to ServiceRequest ID (optional)
#         },
#         "performedDateTime": complete_time,  # Set the performed datetime (next day if no service)
#         "note": [
#             {
#                 "text": "Morning serum magnesium test to be completed next day."
#             }
#         ]
#     }
#
#     # Prepare the request body as a Bundle with the new Procedure entry
#     bundle = {
#         "resourceType": "Bundle",
#         "type": "transaction",
#         "entry": [
#             {
#                 "resource": procedure_entry
#             }
#         ]
#     }
#
#     try:
#         # Make the POST request to create the Procedure entry
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
# # test:
# medication_request_id = "39054"  # Example MedicationRequest ID
# service_request_id = "39056"  # Example ServiceRequest ID (set to None if no service request)
# loinc_code = "2503-9"  # LOINC code for Serum Magnesium Test
# loinc_display = "Serum magnesium (test)"  # Display for the Serum Magnesium Test
#
# # Call the function to create a Procedure entry
# result = post_procedure_request(medication_request_id, loinc_code, loinc_display, service_request_id=None)
# print(result)  # Expected output: "done" or error message
