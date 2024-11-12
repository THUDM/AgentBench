import requests
fhir_base_url = "http://34.132.86.17:8080/fhir/"

def task1_sol(name, dob):
    url = f'{fhir_base_url}Patient'
    if not isinstance(dob, str):
        dob = dob.strftime('%Y-%m-%d')
    last_name = name.split(' ')[-1]
    first_name = ' '.join(name.split(' ')[:-1])
    
    params = {
        'birthdate': dob,
        'given': first_name,
        'family': last_name
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
        data = response.json()
        if data['total'] == 0:
            return "Patient not found"
        return data['entry'][0]['resource']['identifier'][0]['value']
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

assert 'S6540602' == task1_sol('Bobby Klein', '1954-01-02')
assert 'Patient not found' == task1_sol('Kyle', '1999-01-01')

# note: does not consider empty string