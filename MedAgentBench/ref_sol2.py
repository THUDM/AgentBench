import requests
from datetime import datetime
import math

# Define the base URL for the FHIR server
fhir_base_url = "http://34.132.86.17:8080/fhir/"


# Function to calculate the age from the birthdate
def calculate_age(dob: str, today: datetime):
    # Convert the birthdate string to a datetime object
    birth_date = datetime.strptime(dob, '%Y-%m-%d')

    # Calculate the difference in years
    age = today.year - birth_date.year

    # If the birthday hasn't occurred yet this year, subtract 1 from the age
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    # Round up the age
    return math.ceil(age)


# Function to get the patient's age from MRN
def task2_sol(mrn: str):
    # Construct the URL for the FHIR Patient Search endpoint, using MRN in the identifier query parameter
    url = f'{fhir_base_url}Patient?identifier={mrn}'

    try:
        # Send the GET request to search for the patient by MRN
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)

        # Parse the JSON response from the search
        data = response.json()

        # Check if we found any patient data
        if data['total'] == 0:
            return "Patient not found"

        # Iterate through the search results to find the matching MRN
        for entry in data['entry']:
            patient = entry['resource']

            # Extract the MRN from the patient resource
            patient_mrn = next((identifier['value'] for identifier in patient.get('identifier', [])
                                if identifier['type']['coding'][0]['code'] == 'MR'), None)

            # Check if the MRN matches the requested MRN
            if patient_mrn == mrn:
                # Extract the birthdate from the patient resource
                birthdate = patient.get('birthDate', None)
                if not birthdate:
                    return "Birthdate not available"

                # Calculate the patient's age
                today = datetime(2023, 11, 13)  # Fixed today's date as per the example
                age = calculate_age(birthdate, today)

                return age

        # If no matching MRN found, return not found
        return "Patient not found"

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return "Error occurred while retrieving patient data"


# Test
print(task2_sol('S3236936'))  # Test with a valid MRN (replace with the MRN you want to search for)
print(task2_sol('INVALID_MRN'))  # Test with an invalid MRN
