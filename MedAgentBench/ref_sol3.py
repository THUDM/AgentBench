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
#
#
# # test
# print(record_blood_pressure(118, 77, '2023-11-13T10:00:00+00:00'))

import requests

def ref_sol3(method: str, url: str, payload: dict, task_id: int) -> bool:
    """
    Record a blood pressure observation and verify the record with a GET request.

    Args:
        method (str): The HTTP method ('POST').
        url (str): The API endpoint for the Observation resource.
        payload (dict): The observation data.
        task_id (int): The task ID for tracking purposes.

    Returns:
        bool: True if the observation was successfully recorded and verified, False otherwise.
    """
    try:
        # Step 1: Perform the POST request
        print(f"Task ID: {task_id}, Method: {method}, URL: {url}, Payload: {payload}")
        if method == "POST":
            response = requests.post(url, json=payload)
            response.raise_for_status()  # Raise an error for bad responses

            # Step 2: Extract the created resource ID from the POST response
            created_id = payload['resource']['id']

            # Step 3: Perform a GET request to verify the record
            get_response = requests.get(f"{url}/{created_id}")
            get_response.raise_for_status()  # Raise an error for bad responses
            fetched_data = get_response.json()

            # Step 4: Compare the GET response with the original payload
            if fetched_data['id'] == payload['resource']['id'] \
                    and fetched_data['valueQuantity']['value'] == payload['resource']['valueQuantity']['value']:
                return True  # Successful match between POST and GET data
            else:
                return False  # Mismatch between POST and GET data

        else:
            raise ValueError("Invalid method. Use 'POST' for this function.")

    except requests.exceptions.RequestException as e:
        print(f"Task ID: {task_id}, Exception occurred: {e}")
        return False  # Return False if there was an error

# Example usage
if __name__ == "__main__":
    fhir_base_url = "http://34.132.86.17:8080/fhir/"
    observation_url = f"{fhir_base_url}Observation"

    # Example payload for blood pressure
    payload = {
        "resource": {
            "resourceType": "Observation",
            "id": "1001",
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure systolic and diastolic"
                }],
                "text": "Blood pressure systolic and diastolic"
            },
            "valueQuantity": {
                "value": "118/77",
                "unit": "mm Hg",
                "system": "http://unitsofmeasure.org",
                "code": "mm Hg"
            },
            "effectiveDateTime": "2023-11-13T10:00:00+00:00",
            "issued": "2023-11-13T10:00:00+00:00"
        }
    }

    print(ref_sol3("POST", observation_url, payload, 401))  # Expected output: True or False based on the result
