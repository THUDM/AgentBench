# import requests
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
# def task1_sol(name, dob):
#     url = f'{fhir_base_url}Patient'
#     if not isinstance(dob, str):
#         dob = dob.strftime('%Y-%m-%d')
#     last_name = name.split(' ')[-1]
#     first_name = ' '.join(name.split(' ')[:-1])
#
#     params = {
#         'birthdate': dob,
#         'given': first_name,
#         'family': last_name
#     }
#
#     try:
#         response = requests.get(url, params=params)
#         response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
#         data = response.json()
#         if data['total'] == 0:
#             return "Patient not found"
#         return data['entry'][0]['resource']['identifier'][0]['value']
#     except requests.exceptions.RequestException as e:
#         print(f"An error occurred: {e}")
#
# assert 'S6540602' == task1_sol('Bobby Klein', '1954-01-02')
# assert 'Patient not found' == task1_sol('Kyle', '1999-01-01')
#
# # note: does not consider empty string

import requests


def ref_sol1(method: str, url: str, payload: dict, task_id: int) -> bool:
    """
    Fetch patient identifier based on name and date of birth using the API function.

    Args:
        method (str): The HTTP method ('GET').
        url (str): The API endpoint for the Patient resource.
        payload (dict): The query parameters including name and birthdate.
        task_id (int): The task ID for tracking purposes.

    Returns:
        bool: True if the patient was found and identifier retrieved, False otherwise.
    """
    try:
        # Log the request details (for debugging purposes)
        print(f"Task ID: {task_id}, Method: {method}, URL: {url}, Payload: {payload}")

        if method != "GET":
            raise ValueError("Invalid method. Use 'GET' for this function.")

        # Perform the GET request
        response = requests.get(url, params=payload)
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()

        # Process the response
        if data['total'] == 0:
            return False  # Patient not found

        # If a patient is found and identifier is retrieved
        if 'identifier' in data['entry'][0]['resource']:
            return True  # Patient found and identifier retrieved

        return False  # No identifier found, return False

    except requests.exceptions.RequestException as e:
        print(f"Task ID: {task_id}, An error occurred: {e}")
        return False  # Return False if there was an error


# Example usage
if __name__ == "__main__":
    fhir_base_url = "http://34.132.86.17:8080/fhir/"
    patient_url = f"{fhir_base_url}Patient"

    # Test case 1: Valid patient
    payload = {
        'birthdate': '1954-01-02',
        'given': 'Bobby',
        'family': 'Klein'
    }
    print(ref_sol1("GET", patient_url, payload, 101))  # Expected: True

    # Test case 2: Patient not found
    payload = {
        'birthdate': '1999-01-01',
        'given': 'Kyle',
        'family': ''
    }
    print(ref_sol1("GET", patient_url, payload, 102))  # Expected: False
