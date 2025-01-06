from .utils import *

import importlib
# Import the module by its name (without .py extension)
module_name = 'src.server.tasks.medagentbench.refsol'  # Assuming the file is named a.py and is in the same directory
refsol = importlib.import_module(module_name)


def eval(case_data, results, fhir_api_base):
    task_id = case_data['id'].split('_')[0]
    grader_func = getattr(refsol, task_id)
    try:
        if grader_func(case_data, results, fhir_api_base) is True:
            return True
    except Exception as e:
        print(e)
        return False
