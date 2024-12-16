# import requests
# from datetime import datetime, timedelta
#
# # Base FHIR URL for your system
# fhir_base_url = "http://34.132.86.17:8080/fhir/"
#
#
# def get_latest_observation_value(mrn, current_time_str):
#     # Define the URL for the Observation resource
#     url = f'{fhir_base_url}Observation'
#
#     # Parse the current time from the string
#     current_time = datetime.fromisoformat(current_time_str)
#
#     # Define the 24 hours window (from current time)
#     twenty_four_hours_ago = current_time - timedelta(hours=24)
#
#     try:
#         # Make the request to the Observation endpoint (no parameters)
#         response = requests.get(url)
#         response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
#
#         data = response.json()
#
#         # if data['total'] == 0:
#         #     return "No observations found"
#
#         # Initialize to track the most recent observation
#         latest_observation = None
#
#         # Loop through all entries in the response
#         for entry in data['entry']:
#             observation = entry['resource']
#
#             # Extract MRN from the observation and check if it matches the input MRN
#             if 'subject' in observation and observation['subject']['identifier']['value'] == mrn:
#                 effective_date_time = datetime.fromisoformat(observation['effectiveDateTime'])
#
#                 # Check if the observation is within the last 24 hours
#                 if twenty_four_hours_ago <= effective_date_time <= current_time:
#                     if latest_observation is None or effective_date_time > latest_observation['effectiveDateTime']:
#                         latest_observation = {
#                             'value': observation['valueQuantity']['value'],
#                             'unit': observation['valueQuantity']['unit'],
#                             'effectiveDateTime': effective_date_time
#                         }
#
#         # If we found a valid observation, return the value
#         if latest_observation:
#             return latest_observation['value'], latest_observation['unit']
#         else:
#             return "No observation found within the last 24 hours"
#
#     except requests.exceptions.RequestException as e:
#         print(f"An error occurred: {e}")
#         return "Error retrieving data"
#
#
# # test 1:
# # mrn = "S6488980"
# # current_time_str = "2023-11-13T10:15:00+00:00"  # current time
#
# # test 2:
# mrn = "S6488980"
# current_time_str = "2023-03-25T21:05:00+00:00"  # current time
#
# # Call the function and print the result
# result = get_latest_observation_value(mrn, current_time_str)
# if isinstance(result, tuple):
#     value, unit = result
#     print(f"The latest value within the last 24 hours is: {value} {unit}")
# else:
#     print(result)

import requests
from datetime import datetime, timedelta

def ref_sol4(method: str, url: str, payload: dict, task_id: int) -> bool:
    """
    Retrieve the latest observation value for a patient within the last 24 hours using the API function.

    Args:
        method (str): The HTTP method ('GET').
        url (str): The API endpoint for the Observation resource.
        payload (dict): The query parameters including MRN and current time.
        task_id (int): The task ID for tracking purposes.

    Returns:
        bool: True if a valid observation is found, False otherwise.
    """
    try:
        # Log the request details (for debugging purposes)
        print(f"Task ID: {task_id}, Method: {method}, URL: {url}, Payload: {payload}")

        if method != "GET":
            raise ValueError("Invalid method. Use 'GET' for this function.")

        # Extract MRN and current time from payload
        mrn = payload.get('mrn')
        current_time_str = payload.get('current_time')

        if not mrn or not current_time_str:
            return False  # Invalid input, return False

        # Parse the current time and calculate the 24-hour window
        current_time = datetime.fromisoformat(current_time_str)
        twenty_four_hours_ago = current_time - timedelta(hours=24)

        # Perform the GET request
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Initialize to track the most recent observation
        latest_observation = None

        # Loop through all entries in the response
        for entry in data.get('entry', []):
            observation = entry['resource']

            # Extract MRN from the observation and check if it matches the input MRN
            subject_identifier = observation.get('subject', {}).get('identifier', {}).get('value')
            if subject_identifier == mrn:
                effective_date_time = datetime.fromisoformat(observation['effectiveDateTime'])

                # Check if the observation is within the last 24 hours
                if twenty_four_hours_ago <= effective_date_time <= current_time:
                    if latest_observation is None or effective_date_time > latest_observation['effectiveDateTime']:
                        latest_observation = {
                            'value': observation['valueQuantity']['value'],
                            'unit': observation['valueQuantity']['unit'],
                            'effectiveDateTime': effective_date_time
                        }

        # If we found a valid observation, return True
        if latest_observation:
            return True  # Observation found within the last 24 hours

        return False  # No observation found within the last 24 hours

    except requests.exceptions.RequestException as e:
        print(f"Task ID: {task_id}, An error occurred: {e}")
        return False  # Return False if there was an error

# Example usage
if __name__ == "__main__":
    fhir_base_url = "http://34.132.86.17:8080/fhir/"
    observation_url = f"{fhir_base_url}Observation"

    # Test case 1: Valid MRN and time
    payload = {
        'mrn': "S6488980",
        'current_time': "2023-11-13T10:15:00+00:00"
    }
    print(ref_sol4("GET", observation_url, payload, 301))  # Expected output: True or False

    # Test case 2: Invalid MRN or no observation
    payload = {
        'mrn': "INVALID_MRN",
        'current_time': "2023-03-25T21:05:00+00:00"
    }
    print(ref_sol4("GET", observation_url, payload, 302))  # Expected output: False
