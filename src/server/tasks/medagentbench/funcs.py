from patient import Patient

def filter_patients(patients, **kwargs):
    """
    Filters a list of Patient objects based on provided attributes.
    
    Args:
        patients (list): List of Patient objects.
        **kwargs: Attribute-value pairs to filter by (e.g., name="John Doe", dob="1975-04-12").
        
    Returns:
        list: List of filtered Patient objects that match all specified criteria.
    """
    filtered_patients = []

    for patient in patients:
        match = True
        for key, value in kwargs.items():
            if not hasattr(patient, key) or getattr(patient, key) != value:
                match = False
                break
        if match:
            filtered_patients.append(patient)

    return filtered_patients


# Sample list of Patient objects
patients = [
    Patient.from_json('patient_data.json'), #Patient(patient_id="12345", name="John Doe", gender="Male", dob="1979-05-10", address="123 Main St", phone="555-1234", email="johndoe@example.com"),
    Patient(patient_id="67890", name="Jane Smith", gender="Female", dob="1994-07-20", address="456 Elm St", phone="555-5678", email="janesmith@example.com"),
    # Add more Patient objects as needed
]

# Filter by name and DOB
filtered = filter_patients(patients, name="John Doe", dob="1979-05-10")

# Display results
for patient in filtered:
    print(patient)
