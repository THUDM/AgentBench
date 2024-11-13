# import requests
#
# # Define the base URL for the FHIR server
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
#
# def record_blood_pressure(systolic: float, diastolic: float, effective_date: str):
#     """
#     Record a blood pressure observation with dynamically calculated ID.
#
#     :param systolic: Systolic blood pressure value
#     :param diastolic: Diastolic blood pressure value
#     :param effective_date: The date/time when the observation was taken (in ISO 8601 format)
#     :return: "Done" if successful, error message otherwise
#     """
#
#     # Construct the URL for the Observation endpoint
#     observation_url = f"{fhir_base_url}Observation"
#
#     # First, send a GET request to fetch all existing observations
#     try:
#         response = requests.get(observation_url)
#         response.raise_for_status()  # Check for any errors with the GET request
#         data = response.json()
#
#         # Step 1: Get the current highest ID
#         max_id = 0
#         for entry in data['entry']:
#             obs_id = int(entry['resource']['id'])  # Convert id to integer to compare
#             if obs_id > max_id:
#                 max_id = obs_id
#
#         # Step 2: Set the new ID to max_id + 1
#         new_id = max_id + 1
#
#         # Step 3: Create the new blood pressure observation entry with the calculated new_id
#         new_observation = {
#             "fullUrl": f"http://34.132.86.17:8080/fhir/Observation/{new_id}",
#             "resource": {
#                 "resourceType": "Observation",
#                 "id": str(new_id),  # ID is now dynamically set
#                 "status": "final",
#                 "category": [{
#                     "coding": [{
#                         "system": "http://terminology.hl7.org/CodeSystem/observation-category",
#                         "code": "vital-signs",
#                         "display": "Vital Signs"
#                     }]
#                 }],
#                 "code": {
#                     "coding": [{
#                         "system": "http://loinc.org",
#                         "code": "85354-9",
#                         "display": "Blood pressure systolic and diastolic"
#                     }],
#                     "text": "Blood pressure systolic and diastolic"
#                 },
#                 "valueQuantity": {
#                     "value": f'{systolic}/{diastolic}',
#                     "unit": "mm Hg",
#                     "system": "http://unitsofmeasure.org",
#                     "code": "mm Hg"
#                 },
#                 "effectiveDateTime": effective_date,
#                 "issued": effective_date
#             },
#             "search": {
#                 "mode": "match"
#             }
#         }
#
#         # Step 4: Append the new observation to the "entry" list
#         data['entry'].append(new_observation)
#
#         # Step 5: Send the POST request to the server with the updated bundle
#         post_response = requests.post(observation_url, json=data)
#         post_response.raise_for_status()
#
#         # If the POST request was successful, return "Done"
#         return "Done"
#
#     except requests.exceptions.RequestException as e:
#         print(f"An error occurred: {e}")
#         return "Error occurred while recording blood pressure"


# test
print(record_blood_pressure(118, 77, '2023-11-13T10:00:00+00:00'))
