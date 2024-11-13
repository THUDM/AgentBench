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
