import json

class Patient:
    def __init__(self, patient_id, name, dob, gender, address, phone, email, medications=None, lab_tests=None, conditions=None, allergies=None, notes=None):
        # Demographic information
        self.patient_id = patient_id
        self.name = name
        self.dob = dob
        self.gender = gender
        self.address = address
        self.phone = phone
        self.email = email
        
        # Medical data
        self.medications = medications if medications else []
        self.lab_tests = lab_tests if lab_tests else {}
        self.conditions = conditions if conditions else []
        self.allergies = allergies if allergies else []
        self.notes = notes if notes else []

    @classmethod
    def from_json(cls, json_file_path):
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        
        # Initialize from JSON data
        return cls(
            patient_id=data.get("patient_id"),
            name=data.get("name"),
            dob=data.get("dob"),
            gender=data.get("gender"),
            address=data.get("address"),
            phone=data.get("phone"),
            email=data.get("email"),
            medications=data.get("medications"),
            lab_tests=data.get("lab_tests"),
            conditions=data.get("conditions"),
            allergies=data.get("allergies"),
            notes=data.get("notes")
        )

    def add_medication(self, medication_name, dosage, frequency, start_date, end_date=None):
        medication = {
            "medication_name": medication_name,
            "dosage": dosage,
            "frequency": frequency,
            "start_date": start_date,
            "end_date": end_date
        }
        self.medications.append(medication)
    
    def add_lab_test(self, test_name, result, units, date):
        if test_name not in self.lab_tests:
            self.lab_tests[test_name] = []
        self.lab_tests[test_name].append({
            "result": result,
            "units": units,
            "date": date
        })

    def add_condition(self, condition_name, diagnosis_date, status):
        condition = {
            "condition_name": condition_name,
            "diagnosis_date": diagnosis_date,
            "status": status
        }
        self.conditions.append(condition)

    def add_allergy(self, allergen, reaction, severity):
        allergy = {
            "allergen": allergen,
            "reaction": reaction,
            "severity": severity
        }
        self.allergies.append(allergy)

    def add_note(self, note, date):
        self.notes.append({
            "note": note,
            "date": date
        })

    def get_medications(self):
        return self.medications

    def get_lab_tests(self):
        return self.lab_tests

    def get_conditions(self):
        return self.conditions

    def get_allergies(self):
        return self.allergies

    def get_notes(self):
        return self.notes

    def __str__(self):
        return f"Patient ID: {self.patient_id}, Name: {self.name}, DOB: {self.dob}, Gender: {self.gender}"

if __name__ == '__main__':
    # Initialize a Patient object from a JSON file
    patient = Patient.from_json("patient_data.json")

    # Print the patient information
    print(patient)

    # Access the patient's data
    print(patient.get_medications())
    print(patient.get_lab_tests())
    print(patient.get_conditions())
    print(patient.get_allergies())
    print(patient.get_notes())
