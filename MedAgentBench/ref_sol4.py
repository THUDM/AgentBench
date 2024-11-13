import requests
from datetime import datetime, timedelta

# Base FHIR URL for your system
fhir_base_url = "http://34.132.86.17:8080/fhir/"


def get_latest_observation_value(mrn, current_time_str):
    # Define the URL for the Observation resource
    url = f'{fhir_base_url}Observation'

    # Parse the current time from the string
    current_time = datetime.fromisoformat(current_time_str)

    # Define the 24 hours window (from current time)
    twenty_four_hours_ago = current_time - timedelta(hours=24)

    try:
        # Make the request to the Observation endpoint (no parameters)
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        # if data['total'] == 0:
        #     return "No observations found"

        # Initialize to track the most recent observation
        latest_observation = None

        # Loop through all entries in the response
        for entry in data['entry']:
            observation = entry['resource']

            # Extract MRN from the observation and check if it matches the input MRN
            if 'subject' in observation and observation['subject']['identifier']['value'] == mrn:
                effective_date_time = datetime.fromisoformat(observation['effectiveDateTime'])

                # Check if the observation is within the last 24 hours
                if twenty_four_hours_ago <= effective_date_time <= current_time:
                    if latest_observation is None or effective_date_time > latest_observation['effectiveDateTime']:
                        latest_observation = {
                            'value': observation['valueQuantity']['value'],
                            'unit': observation['valueQuantity']['unit'],
                            'effectiveDateTime': effective_date_time
                        }

        # If we found a valid observation, return the value
        if latest_observation:
            return latest_observation['value'], latest_observation['unit']
        else:
            return "No observation found within the last 24 hours"

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return "Error retrieving data"


# test 1:
# mrn = "S6488980"
# current_time_str = "2023-11-13T10:15:00+00:00"  # current time

# test 2:
mrn = "S6488980"
current_time_str = "2023-03-25T21:05:00+00:00"  # current time

# Call the function and print the result
result = get_latest_observation_value(mrn, current_time_str)
if isinstance(result, tuple):
    value, unit = result
    print(f"The latest value within the last 24 hours is: {value} {unit}")
else:
    print(result)
